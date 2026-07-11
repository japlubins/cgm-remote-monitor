#!/usr/bin/env python3
"""Interfaz física del streamer HiFi: pantalla OLED + encoder rotatorio.

Controles:
  - Girar el encoder ....... navegar por listas / cambiar de pista en "Reproduciendo"
  - Pulsar el encoder ...... seleccionar / play-pausa en "Reproduciendo"
  - Botón atrás ............ volver / abrir el menú desde "Reproduciendo"

Habla con el demonio MPD local: la pantalla muestra todo lo que se
reproduce vía MPD (biblioteca, playlists, radios y UPnP a través de
upmpdcli). AirPlay y Spotify Connect van directos a ALSA y no aparecen.
"""

import socket
import subprocess
import threading
import time

from gpiozero import Button, RotaryEncoder
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from mpd import MPDClient
from mpd import ConnectionError as MPDConnectionError
from PIL import ImageFont

# ─── Pines (BCM) y hardware ──────────────────────────────────────────────────
PIN_ENC_A = 17      # CLK del encoder
PIN_ENC_B = 27      # DT  del encoder
PIN_ENC_SW = 22     # pulsador del encoder
PIN_BACK = 23       # botón "atrás"
I2C_PORT = 1        # bus I2C de la Pi (SDA=GPIO2, SCL=GPIO3)
I2C_ADDRESS = 0x3C  # dirección habitual del SSD1306

RADIOS_FILE = "/etc/streamer-ui/radios.conf"

FONT = ImageFont.load_default()
LINE_H = 12          # alto de línea en píxeles
VISIBLE_LINES = 5    # líneas que caben en 128x64 dejando sitio a la cabecera


def load_radios():
    """Lee radios.conf: una emisora por línea, formato 'Nombre|URL'."""
    radios = []
    try:
        with open(RADIOS_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "|" in line:
                    name, url = line.split("|", 1)
                    radios.append((name.strip(), url.strip()))
    except FileNotFoundError:
        pass
    return radios


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "sin red"
    finally:
        s.close()


class Mpd:
    """Cliente MPD con reconexión automática."""

    def __init__(self, host="localhost", port=6600):
        self._host, self._port = host, port
        self._client = MPDClient()
        self._client.timeout = 5
        self._lock = threading.Lock()

    def _call(self, method, *args):
        with self._lock:
            for attempt in (1, 2):
                try:
                    return getattr(self._client, method)(*args)
                except (MPDConnectionError, OSError):
                    try:
                        self._client.disconnect()
                    except Exception:
                        pass
                    if attempt == 2:
                        raise
                    self._client.connect(self._host, self._port)

    def status(self):
        return self._call("status")

    def current(self):
        return self._call("currentsong")

    def toggle(self):
        state = self.status().get("state")
        if state == "play":
            self._call("pause", 1)
        elif state == "pause":
            self._call("pause", 0)
        else:
            self._call("play")

    def next(self):
        self._call("next")

    def prev(self):
        self._call("previous")

    def playlists(self):
        return sorted(p["playlist"] for p in self._call("listplaylists"))

    def play_playlist(self, name):
        self._call("clear")
        self._call("load", name)
        self._call("play")

    def play_url(self, url):
        self._call("clear")
        self._call("add", url)
        self._call("play")

    def queue(self):
        return self._call("playlistinfo")

    def play_pos(self, pos):
        self._call("play", pos)


class UI:
    def __init__(self):
        self.mpd = Mpd()
        serial = i2c(port=I2C_PORT, address=I2C_ADDRESS)
        self.device = ssd1306(serial)

        self.lock = threading.Lock()
        self.redraw = threading.Event()

        # pila de pantallas; cada una: {"kind": ..., "title": ..., "items": [...],
        #                               "actions": [...], "sel": 0}
        self.stack = [{"kind": "now"}]

        self.encoder = RotaryEncoder(PIN_ENC_A, PIN_ENC_B, max_steps=0)
        self.encoder.when_rotated_clockwise = lambda: self.on_rotate(+1)
        self.encoder.when_rotated_counter_clockwise = lambda: self.on_rotate(-1)
        self.btn_select = Button(PIN_ENC_SW, pull_up=True, bounce_time=0.05)
        self.btn_select.when_pressed = self.on_select
        self.btn_back = Button(PIN_BACK, pull_up=True, bounce_time=0.05)
        self.btn_back.when_pressed = self.on_back

    # ─── construcción de pantallas ───────────────────────────────────────────
    def screen_menu(self):
        return {
            "kind": "list",
            "title": "Menú",
            "items": ["Playlists", "Radios", "Cola", "Sistema"],
            "actions": ["playlists", "radios", "queue", "system"],
            "sel": 0,
        }

    def screen_playlists(self):
        names = self.mpd.playlists()
        return {
            "kind": "list",
            "title": "Playlists",
            "items": names or ["(no hay playlists)"],
            "actions": [("load_playlist", n) for n in names] or [None],
            "sel": 0,
        }

    def screen_radios(self):
        radios = load_radios()
        return {
            "kind": "list",
            "title": "Radios",
            "items": [n for n, _ in radios] or ["(edita radios.conf)"],
            "actions": [("play_url", u) for _, u in radios] or [None],
            "sel": 0,
        }

    def screen_queue(self):
        songs = self.mpd.queue()
        items = [s.get("title") or s.get("name") or s.get("file", "?") for s in songs]
        return {
            "kind": "list",
            "title": "Cola",
            "items": items or ["(cola vacía)"],
            "actions": [("play_pos", i) for i in range(len(songs))] or [None],
            "sel": 0,
        }

    def screen_system(self):
        return {
            "kind": "list",
            "title": "Sistema",
            "items": [f"IP: {local_ip()}", "Reiniciar", "Apagar"],
            "actions": [None, ("cmd", "reboot"), ("cmd", "poweroff")],
            "sel": 0,
        }

    # ─── eventos de los controles ────────────────────────────────────────────
    def on_rotate(self, step):
        with self.lock:
            top = self.stack[-1]
            if top["kind"] == "now":
                (self.mpd.next if step > 0 else self.mpd.prev)()
            else:
                top["sel"] = max(0, min(len(top["items"]) - 1, top["sel"] + step))
        self.redraw.set()

    def on_select(self):
        with self.lock:
            top = self.stack[-1]
            if top["kind"] == "now":
                self.mpd.toggle()
            else:
                action = top["actions"][top["sel"]]
                self.run_action(action)
        self.redraw.set()

    def on_back(self):
        with self.lock:
            if self.stack[-1]["kind"] == "now":
                self.stack.append(self.screen_menu())
            else:
                self.stack.pop()
        self.redraw.set()

    def run_action(self, action):
        if action is None:
            return
        if action == "playlists":
            self.stack.append(self.screen_playlists())
        elif action == "radios":
            self.stack.append(self.screen_radios())
        elif action == "queue":
            self.stack.append(self.screen_queue())
        elif action == "system":
            self.stack.append(self.screen_system())
        else:
            verb, arg = action
            if verb == "load_playlist":
                self.mpd.play_playlist(arg)
            elif verb == "play_url":
                self.mpd.play_url(arg)
            elif verb == "play_pos":
                self.mpd.play_pos(arg)
            elif verb == "cmd":
                subprocess.Popen(["systemctl", arg])
                return
            # tras lanzar reproducción, volver a "Reproduciendo"
            self.stack = [{"kind": "now"}]

    # ─── dibujo ──────────────────────────────────────────────────────────────
    def draw(self):
        with self.lock:
            top = dict(self.stack[-1])
            if top["kind"] == "list":
                top["items"] = list(self.stack[-1]["items"])

        with canvas(self.device) as dc:
            if top["kind"] == "now":
                self.draw_now(dc)
            else:
                self.draw_list(dc, top)

    def draw_now(self, dc):
        try:
            status = self.mpd.status()
            song = self.mpd.current()
        except Exception:
            dc.text((0, 26), "MPD no disponible...", font=FONT, fill="white")
            return

        state = {"play": ">", "pause": "||", "stop": "[]"}.get(status.get("state"), "?")
        title = song.get("title") or song.get("name") or song.get("file", "(nada)")
        artist = song.get("artist", "")

        dc.text((0, 0), f"{state} Reproduciendo", font=FONT, fill="white")
        dc.line((0, 13, 127, 13), fill="white")
        dc.text((0, 20), title[:21], font=FONT, fill="white")
        dc.text((0, 32), artist[:21], font=FONT, fill="white")

        elapsed = float(status.get("elapsed", 0))
        duration = float(status.get("duration", 0) or 0)
        if duration:
            frac = min(1.0, elapsed / duration)
            dc.rectangle((0, 52, 127, 58), outline="white")
            dc.rectangle((0, 52, int(127 * frac), 58), outline="white", fill="white")

    def draw_list(self, dc, top):
        dc.text((0, 0), top["title"], font=FONT, fill="white")
        dc.line((0, 11, 127, 11), fill="white")
        visible = VISIBLE_LINES - 1  # la cabecera ocupa una línea
        first = max(0, min(top["sel"] - visible // 2, len(top["items"]) - visible))
        for row, idx in enumerate(range(first, min(len(top["items"]), first + visible))):
            y = 14 + row * LINE_H
            marker = ">" if idx == top["sel"] else " "
            dc.text((0, y), f"{marker}{top['items'][idx][:20]}", font=FONT, fill="white")

    # ─── bucle principal ─────────────────────────────────────────────────────
    def run(self):
        while True:
            try:
                self.draw()
            except Exception:
                pass
            # refresco: inmediato si hay interacción, cada 1 s en reposo
            self.redraw.wait(timeout=1.0)
            self.redraw.clear()


if __name__ == "__main__":
    UI().run()

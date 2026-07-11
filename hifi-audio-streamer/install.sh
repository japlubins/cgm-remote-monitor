#!/usr/bin/env bash
#
# Instalador del audio streamer HiFi para Raspberry Pi OS Lite (bookworm o posterior).
# Monta: MPD + shairport-sync (AirPlay) + upmpdcli (UPnP/DLNA) + raspotify (opcional).
#
# Uso:  sudo ./install.sh
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Ejecuta con sudo: sudo ./install.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"

# ─── Nombre del dispositivo en la red ────────────────────────────────────────
read -rp "Nombre del streamer en la red [HiFi Pi]: " DEVICE_NAME
DEVICE_NAME="${DEVICE_NAME:-HiFi Pi}"

# ─── Detectar tarjetas de audio y elegir el DAC ──────────────────────────────
echo
echo "Tarjetas de audio detectadas:"
aplay -l | grep '^card' || { echo "No se detectó ninguna tarjeta. ¿Está conectado el DAC / activado el overlay del HAT?" >&2; exit 1; }
echo
DEFAULT_CARD="$(aplay -l | grep '^card' | head -n1 | sed 's/^card \([0-9]*\).*/\1/')"
read -rp "Número de tarjeta a usar [$DEFAULT_CARD]: " CARD
CARD="${CARD:-$DEFAULT_CARD}"

# Nombre estable de la tarjeta (mejor que el número, que puede cambiar al arrancar)
CARD_NAME="$(cat "/proc/asound/card${CARD}/id")"
ALSA_DEVICE="hw:CARD=${CARD_NAME},DEV=0"
echo "Se usará el dispositivo ALSA: $ALSA_DEVICE"

# ─── Paquetes base ───────────────────────────────────────────────────────────
echo
echo "Instalando paquetes..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    mpd mpc \
    shairport-sync \
    upmpdcli \
    alsa-utils curl

# ─── Desplegar configuraciones ──────────────────────────────────────────────
render() {  # sustituye placeholders y escribe el fichero destino
    sed -e "s|@ALSA_DEVICE@|$ALSA_DEVICE|g" \
        -e "s|@CARD_NAME@|$CARD_NAME|g" \
        -e "s|@DEVICE_NAME@|$DEVICE_NAME|g" \
        "$1" > "$2"
}

# Copia de seguridad la primera vez
for f in /etc/mpd.conf /etc/shairport-sync.conf /etc/upmpdcli.conf; do
    [[ -f "$f" && ! -f "$f.orig" ]] && cp "$f" "$f.orig"
done

render "$CONFIG_DIR/mpd.conf"            /etc/mpd.conf
render "$CONFIG_DIR/shairport-sync.conf" /etc/shairport-sync.conf
render "$CONFIG_DIR/upmpdcli.conf"       /etc/upmpdcli.conf
render "$CONFIG_DIR/asound.conf.example" /etc/asound.conf

mkdir -p /var/lib/mpd/music /var/lib/mpd/playlists
chown -R mpd:audio /var/lib/mpd

# ─── Spotify Connect (raspotify) — opcional ─────────────────────────────────
echo
read -rp "¿Instalar Spotify Connect (raspotify)? Requiere cuenta Spotify [S/n]: " SPOTIFY
if [[ ! "${SPOTIFY,,}" =~ ^n ]]; then
    if ! dpkg -s raspotify >/dev/null 2>&1; then
        curl -sSL https://dtcooper.github.io/raspotify/install.sh | sh
    fi
    # Configurar nombre y salida
    sed -i \
        -e "s|^#\?LIBRESPOT_NAME=.*|LIBRESPOT_NAME=\"$DEVICE_NAME\"|" \
        -e "s|^#\?LIBRESPOT_DEVICE=.*|LIBRESPOT_DEVICE=\"$ALSA_DEVICE\"|" \
        -e "s|^#\?LIBRESPOT_BITRATE=.*|LIBRESPOT_BITRATE=\"320\"|" \
        /etc/raspotify/conf
    systemctl enable --now raspotify
    systemctl restart raspotify
fi

# ─── Arrancar servicios ──────────────────────────────────────────────────────
systemctl enable --now mpd shairport-sync upmpdcli
systemctl restart mpd shairport-sync upmpdcli

echo
echo "════════════════════════════════════════════════════════════"
echo " Listo. \"$DEVICE_NAME\" ya está disponible en tu red como:"
echo "   • AirPlay (shairport-sync)"
echo "   • Renderizador UPnP/DLNA (upmpdcli)"
dpkg -s raspotify >/dev/null 2>&1 && echo "   • Spotify Connect (raspotify)"
echo "   • Servidor MPD en el puerto 6600"
echo
echo " Prueba rápida:"
echo "   mpc add https://icecast.rtve.es/radioclasica && mpc play"
echo "════════════════════════════════════════════════════════════"

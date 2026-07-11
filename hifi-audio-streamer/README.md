# Audio Streamer HiFi con Raspberry Pi

Proyecto para convertir una Raspberry Pi en un streamer de audio de calidad HiFi,
conectado a tu equipo (amplificador/DAC externo) usando exclusivamente software libre.

El resultado final es un aparato autónomo con **pantalla OLED y encoder
rotatorio** para navegar por playlists y radios sin necesidad de móvil
(ver sección 6), que además aparece en tu red como:

- **Salida AirPlay** (desde iPhone/iPad/Mac) — vía `shairport-sync`
- **Spotify Connect** (desde la app oficial de Spotify) — vía `raspotify` (librespot)
- **Renderizador UPnP/DLNA** (desde BubbleUPnP, Audirvana, JRiver, etc.) — vía `upmpdcli`
- **Servidor MPD** para reproducir tu biblioteca local o streams de radio,
  controlado desde el móvil con apps libres como M.A.L.P. (Android) o MPDeck

---

## 1. Hardware recomendado

| Componente | Recomendación | Notas |
|---|---|---|
| Raspberry Pi | Pi 3B+, Pi 4 o Zero 2 W | Cualquiera sobra para audio; la Pi 4 es la más cómoda |
| Salida de audio | **DAC USB** o **DAC HAT** | Ver abajo. **No uses el jack de 3,5 mm**: su calidad es mala |
| Alimentación | Fuente oficial o de calidad | Las fuentes ruidosas introducen interferencias audibles |
| Red | Ethernet si es posible | WiFi funciona, pero cable = cero cortes |
| Almacenamiento | microSD 16 GB+ | Con USB/SSD si vas a guardar tu biblioteca en la Pi |

### Opciones de salida hacia tu equipo HiFi

1. **DAC USB externo** (la opción más flexible): conecta la Pi por USB a cualquier
   DAC (Topping, SMSL, iFi, o la entrada USB de tu amplificador si la tiene).
   Linux los soporta sin drivers (clase USB Audio 2.0), incluyendo hi-res y DSD (DoP).
2. **DAC HAT sobre la Pi**: placas como HiFiBerry DAC+/DAC2, IQaudIO DAC Pro,
   Allo Boss. Salida RCA analógica directa al amplificador. Compacto y muy buena calidad.
3. **HAT con salida digital (S/PDIF)**: HiFiBerry Digi+, Allo DigiOne. Ideal si tu
   equipo ya tiene un buen DAC con entrada coaxial/óptica.

---

## 2. Elegir el software: distro llave en mano vs. montaje propio

### Opción A — Distribuciones listas para usar

Si quieres el camino rápido, estas distros libres/gratuitas hacen todo con interfaz web:

| Distro | Licencia | Puntos fuertes |
|---|---|---|
| [moOde Audio](https://moodeaudio.org) | GPLv3 (100 % libre) | La más completa y cuidada en calidad de audio; AirPlay, Spotify, UPnP, radio, multiroom |
| [piCorePlayer](https://www.picoreplayer.org) | Libre | Ultraligera, corre en RAM; ideal con Lyrion (Logitech Media Server) |
| [Volumio](https://volumio.com) | Núcleo open source | Interfaz muy pulida; funciones avanzadas de pago |

**Recomendación:** si no quieres mantener nada a mano, usa **moOde**: es software
libre de verdad y su rendimiento sonoro es excelente. Grabas la imagen con
Raspberry Pi Imager y listo.

### Opción B — Montaje propio sobre Raspberry Pi OS Lite (este proyecto)

Si prefieres controlar cada pieza (y aprender por el camino), este repositorio
incluye un instalador que monta el stack completo sobre Raspberry Pi OS Lite:

```
MPD  ──────────────┐
shairport-sync ────┤──►  ALSA (salida directa, bit-perfect)  ──►  DAC  ──►  Ampli
raspotify ─────────┤
upmpdcli ──► MPD ──┘
```

---

## 3. Instalación (Opción B)

### 3.1 Preparar la Pi

1. Graba **Raspberry Pi OS Lite (64-bit)** con Raspberry Pi Imager.
   En las opciones del Imager configura usuario, WiFi (si no usas cable) y **SSH**.
2. Arranca la Pi y entra por SSH: `ssh usuario@raspberrypi.local`
3. Actualiza: `sudo apt update && sudo apt full-upgrade -y`

### 3.2 Si usas un DAC HAT: activar el overlay

Edita `/boot/firmware/config.txt` (en sistemas antiguos, `/boot/config.txt`):

```ini
# Desactivar el audio interno (jack/HDMI) para que el DAC sea la única tarjeta
dtparam=audio=off

# Activar tu HAT (ejemplos; usa solo UNA línea, la de tu placa):
dtoverlay=hifiberry-dacplus     # HiFiBerry DAC+ / DAC2
#dtoverlay=iqaudio-dacplus      # IQaudIO DAC Pro
#dtoverlay=allo-boss-dac-pcm512x-audio  # Allo Boss
```

Reinicia y comprueba que aparece la tarjeta: `aplay -l`

Con **DAC USB** no hay que tocar nada: conéctalo y verifica con `aplay -l`.

### 3.3 Ejecutar el instalador

```bash
git clone <este-repo>
cd hifi-audio-streamer
sudo ./install.sh
```

El script:

1. Instala `mpd`, `mpc`, `shairport-sync`, `upmpdcli` y utilidades de ALSA.
2. Instala `raspotify` (Spotify Connect) desde su repositorio oficial (opcional, pregunta).
3. Despliega las configuraciones de `config/` apuntando a tu tarjeta de audio.
4. Habilita y arranca todos los servicios.

Al terminar, el dispositivo aparecerá en tu red como **"HiFi Pi"** (nombre
configurable al inicio del script).

### 3.4 Probar

```bash
# ¿Suena? Ruido blanco 2 segundos por la salida por defecto:
speaker-test -c 2 -t wav -l 1

# Radio por MPD:
mpc add https://icecast.rtve.es/radioclasica  # Radio Clásica (RNE)
mpc play
```

Desde el móvil: abre Spotify y elige "HiFi Pi" en dispositivos, o envía audio
por AirPlay desde un dispositivo Apple.

---

## 4. Calidad de audio: conseguir salida bit-perfect

Para que el audio llegue al DAC sin alteraciones:

- **Salida directa a hardware** (`hw:`) en MPD, sin `dmix` ni PulseAudio/PipeWire.
  El `mpd.conf` incluido ya lo hace.
- **Sin control de volumen software**: en `mpd.conf` va `mixer_type "none"`
  (controla el volumen en tu amplificador). Si necesitas volumen desde el móvil,
  cámbialo a `"software"` sabiendo que reduce ligeramente la resolución.
- **Sin remuestreo**: MPD negocia la frecuencia nativa del archivo con el DAC.
  Comprueba la frecuencia real que recibe el DAC mientras suena:

  ```bash
  cat /proc/asound/card*/pcm0p/sub0/hw_params
  ```

  Debe coincidir con la del archivo (44100 para CD/Spotify, 96000/192000 para hi-res).

- Nota: AirPlay clásico siempre transmite a 44,1 kHz/16 bit (limitación del protocolo).

---

## 5. Control diario

| Fuente | Cómo se controla |
|---|---|
| Spotify | App oficial → menú de dispositivos → "HiFi Pi" |
| AirPlay | Selector de audio de iOS/macOS |
| Biblioteca local / radio (MPD) | M.A.L.P. o MPDroid (Android, en F-Droid), MPDeck/Persephone (iOS), `mpc` en terminal, o [myMPD](https://jcorporation.github.io/myMPD/) como interfaz web |
| UPnP/DLNA | BubbleUPnP (Android), o cualquier control point apuntando al renderizador |

Para tu música local, cópiala a `/var/lib/mpd/music` (o monta ahí un USB/NAS
por `fstab`) y ejecuta `mpc update`.

---

## 6. Modo standalone: pantalla y controles físicos

Para usar el streamer como un aparato autónomo — sin necesidad de móvil ni
navegador — el proyecto incluye una interfaz física: una pantalla OLED que
muestra lo que suena y un encoder rotatorio para navegar por menús
(playlists, radios, cola y sistema).

### 6.1 Hardware necesario

| Pieza | Modelo recomendado | Precio aprox. |
|---|---|---|
| Pantalla | OLED 0,96" o 1,3" **SSD1306/SH1106, I2C** (128×64) | 3–6 € |
| Control | **Encoder rotatorio KY-040** (girar + pulsar) | 1–2 € |
| Botón | Pulsador momentáneo (botón "atrás") | <1 € |

### 6.2 Cableado (pines BCM)

```
OLED (I2C)                Encoder KY-040            Botón atrás
────────────              ──────────────            ───────────
VCC → 3V3 (pin 1)         CLK → GPIO17 (pin 11)     una pata → GPIO23 (pin 16)
GND → GND  (pin 6)        DT  → GPIO27 (pin 13)     otra pata → GND (pin 14)
SDA → GPIO2 (pin 3)       SW  → GPIO22 (pin 15)
SCL → GPIO3 (pin 5)       +   → 3V3, GND → GND
```

> Los pines son configurables al principio de `ui/streamer_ui.py`.
> Ojo si usas un DAC HAT: consulta qué GPIO deja libres tu placa
> (los HAT de HiFiBerry/IQaudIO usan I2S — GPIO 18/19/20/21 — y dejan
> libres los de arriba; el bus I2C es compartible sin problema).

### 6.3 Instalación

```bash
sudo ./install-ui.sh
```

Instala las dependencias Python en un entorno virtual (`/opt/streamer-ui`),
activa el bus I2C y deja corriendo el servicio `streamer-ui` que arranca
solo al encender la Pi.

### 6.4 Manejo

| Gesto | En "Reproduciendo" | En listas/menús |
|---|---|---|
| Girar encoder | Pista siguiente/anterior | Mover la selección |
| Pulsar encoder | Play / pausa | Seleccionar |
| Botón atrás | Abrir el menú | Volver |

El menú da acceso a **Playlists** (las guardadas en MPD), **Radios**
(emisoras definidas en `/etc/streamer-ui/radios.conf`), la **Cola** actual
y **Sistema** (ver la IP, reiniciar, apagar de forma segura).

La pantalla muestra lo que se reproduce a través de MPD (biblioteca,
playlists, radios y UPnP vía upmpdcli). AirPlay y Spotify Connect suenan
igual, pero van directos a ALSA y no aparecen en pantalla.

### 6.5 Alternativa: pantalla táctil

Si prefieres una interfaz gráfica completa, usa la **pantalla táctil oficial
de 7"** (u otra HDMI/DSI con touch):

- Con **moOde Audio** basta activar su "local display" en la configuración:
  muestra la propia interfaz web en la pantalla, con carátulas y todo.
- En el montaje propio de este repo: instala [myMPD](https://jcorporation.github.io/myMPD/)
  y lanza Chromium en modo kiosco apuntando a `http://localhost` — buena
  opción si tu prioridad es navegar la biblioteca con carátulas.

La OLED + encoder gasta menos, arranca al instante y da un aspecto más de
"aparato HiFi"; la táctil es más cómoda para bibliotecas grandes.

---

## 7. Extras opcionales

- **Multiroom**: [Snapcast](https://github.com/badaix/snapcast) sincroniza varias
  Pis en distintas habitaciones.
- **Bluetooth como fuente**: `bluez-alsa` permite enviar audio desde el móvil por
  Bluetooth (calidad inferior a las opciones de red; úsalo solo como comodidad).
- **Ecualización/corrección de sala**: CamillaDSP como pipeline de convolución
  entre ALSA y el DAC.

## Estructura del proyecto

```
hifi-audio-streamer/
├── README.md                  # esta guía
├── install.sh                 # instalador del stack de audio (Raspberry Pi OS Lite)
├── install-ui.sh              # instalador de la interfaz física (pantalla + encoder)
├── config/
│   ├── mpd.conf               # MPD con salida ALSA directa (bit-perfect)
│   ├── shairport-sync.conf    # receptor AirPlay
│   ├── upmpdcli.conf          # renderizador UPnP → MPD
│   └── asound.conf.example    # ALSA por defecto apuntando al DAC
└── ui/
    ├── streamer_ui.py         # app de la pantalla OLED + encoder
    ├── radios.conf            # emisoras del menú "Radios"
    ├── requirements.txt       # dependencias Python
    └── streamer-ui.service    # servicio systemd
```

Licencia: los scripts y configuraciones de esta carpeta se publican bajo GPLv3,
igual que el software que instalan.

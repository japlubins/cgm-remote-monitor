#!/usr/bin/env bash
#
# Instalador de la interfaz física (pantalla OLED + encoder rotatorio).
# Ejecutar DESPUÉS de install.sh:  sudo ./install-ui.sh
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Ejecuta con sudo: sudo ./install-ui.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$SCRIPT_DIR/ui"
DEST=/opt/streamer-ui

echo "Instalando dependencias del sistema..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-venv python3-dev i2c-tools libgpiod2

echo "Activando el bus I2C..."
raspi-config nonint do_i2c 0 || echo "(raspi-config no disponible; activa I2C a mano si hace falta)"

echo "Creando entorno Python en $DEST ..."
mkdir -p "$DEST"
python3 -m venv "$DEST/venv"
"$DEST/venv/bin/pip" install --upgrade pip
"$DEST/venv/bin/pip" install -r "$UI_DIR/requirements.txt"

install -m 0755 "$UI_DIR/streamer_ui.py" "$DEST/streamer_ui.py"

mkdir -p /etc/streamer-ui
# No machacar radios personalizadas en reinstalaciones
[[ -f /etc/streamer-ui/radios.conf ]] || install -m 0644 "$UI_DIR/radios.conf" /etc/streamer-ui/radios.conf

install -m 0644 "$UI_DIR/streamer-ui.service" /etc/systemd/system/streamer-ui.service
systemctl daemon-reload
systemctl enable --now streamer-ui

echo
echo "════════════════════════════════════════════════════════════"
echo " Interfaz instalada y arrancada."
echo
echo " Si la pantalla no se enciende:"
echo "   • Comprueba el cableado y que aparece en:  i2cdetect -y 1"
echo "     (debería verse un dispositivo en 3c)"
echo "   • Logs del servicio:  journalctl -u streamer-ui -f"
echo
echo " Emisoras del menú Radios:  /etc/streamer-ui/radios.conf"
echo "════════════════════════════════════════════════════════════"

#!/bin/bash
# KeyMesh installer for Raspberry Pi Zero 2 W
# Run as root: sudo bash install.sh
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo bash install.sh"
    exit 1
fi

echo "=== KeyMesh Installer ==="

# 1. Install dependencies
echo "[1/6] Installing packages..."
apt-get update -qq
apt-get install -y -qq hostapd dnsmasq python3 python3-pip > /dev/null
pip3 install --break-system-packages websockets 2>/dev/null || pip3 install websockets
# Stop them from auto-starting — keymesh manages them
systemctl disable hostapd 2>/dev/null || true
systemctl stop hostapd 2>/dev/null || true
systemctl disable dnsmasq 2>/dev/null || true
systemctl stop dnsmasq 2>/dev/null || true

# 2. Enable USB gadget overlay (dwc2)
echo "[2/6] Configuring USB gadget overlay..."
CONFIG_TXT=""
for f in /boot/firmware/config.txt /boot/config.txt; do
    if [ -f "$f" ]; then CONFIG_TXT="$f"; break; fi
done
if [ -z "$CONFIG_TXT" ]; then
    echo "ERROR: Cannot find config.txt"
    exit 1
fi

if ! grep -q "^dtoverlay=dwc2" "$CONFIG_TXT"; then
    echo "dtoverlay=dwc2" >> "$CONFIG_TXT"
    echo "  Added dtoverlay=dwc2 to $CONFIG_TXT"
fi

# Ensure dwc2 and libcomposite load at boot
if ! grep -q "^dwc2" /etc/modules; then
    echo "dwc2" >> /etc/modules
fi
if ! grep -q "^libcomposite" /etc/modules; then
    echo "libcomposite" >> /etc/modules
fi

# 3. Configure UART
echo "[3/6] Configuring UART..."
# Enable UART
if ! grep -q "^enable_uart=1" "$CONFIG_TXT"; then
    echo "enable_uart=1" >> "$CONFIG_TXT"
fi

# Disable serial console so we can use UART for bridging
CMDLINE=""
for f in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
    if [ -f "$f" ]; then CMDLINE="$f"; break; fi
done
if [ -n "$CMDLINE" ]; then
    if grep -q "console=serial0" "$CMDLINE"; then
        sed -i 's/console=serial0,[0-9]* //g' "$CMDLINE"
        echo "  Removed serial console from $CMDLINE"
    fi
fi

# 4. Install KeyMesh files
echo "[4/6] Installing KeyMesh to /opt/keymesh..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /opt/keymesh/www
for f in main.py hid.py uart_bridge.py web.py tcp.py net.py ring_buffer.py keymap.py config.json gadget.sh; do
    cp "$SCRIPT_DIR/$f" /opt/keymesh/
done
cp "$SCRIPT_DIR/www/index.html" /opt/keymesh/www/
chmod +x /opt/keymesh/gadget.sh

# 5. Install systemd service
echo "[5/6] Installing systemd service..."
cat > /etc/systemd/system/keymesh.service << 'UNIT'
[Unit]
Description=KeyMesh Remote Recovery Device
After=network.target
Wants=network.target

[Service]
Type=simple
ExecStartPre=/opt/keymesh/gadget.sh
ExecStart=/usr/bin/python3 /opt/keymesh/main.py
WorkingDirectory=/opt/keymesh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable keymesh.service

# 6. Done
echo "[6/6] Done!"
echo ""
echo "=== Next steps ==="
echo "1. Edit /opt/keymesh/config.json if you want to change WiFi settings"
echo "2. Reboot: sudo reboot"
echo "3. After reboot:"
echo "   - Connect to 'keymesh' WiFi"
echo "   - Open http://192.168.4.1 in browser"
echo "   - Or: nc 192.168.4.1 4444"
echo ""
echo "The USB data port (not power) connects to the target server."

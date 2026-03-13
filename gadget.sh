#!/bin/bash
# Configure USB HID keyboard gadget via configfs.
# Run as root before starting keymesh.
set -e

GADGET_DIR="/sys/kernel/config/usb_gadget/keymesh"

# Already configured?
if [ -d "$GADGET_DIR" ]; then
    echo "USB gadget already configured"
    exit 0
fi

# Load required kernel module
modprobe libcomposite

# Create gadget
mkdir -p "$GADGET_DIR"
cd "$GADGET_DIR"

echo 0x1209 > idVendor      # pid.codes open source VID
echo 0xC0DE > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

# Strings
mkdir -p strings/0x409
echo "KeyMesh"              > strings/0x409/manufacturer
echo "KeyMesh HID Keyboard" > strings/0x409/product
echo "000000001"            > strings/0x409/serialnumber

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "KeyMesh Config" > configs/c.1/strings/0x409/configuration
echo 500 > configs/c.1/MaxPower

# HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol      # Keyboard
echo 1 > functions/hid.usb0/subclass       # Boot interface
echo 8 > functions/hid.usb0/report_length

# Standard keyboard HID report descriptor (45 bytes)
echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x01\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' \
    > functions/hid.usb0/report_desc

# Link function to configuration
ln -s functions/hid.usb0 configs/c.1/

# Find UDC (USB Device Controller) and bind
UDC=$(ls /sys/class/udc | head -1)
if [ -z "$UDC" ]; then
    echo "ERROR: No USB Device Controller found"
    echo "Make sure dtoverlay=dwc2 is in /boot/firmware/config.txt"
    exit 1
fi
echo "$UDC" > UDC

echo "USB HID gadget configured on $UDC"
echo "/dev/hidg0 ready"

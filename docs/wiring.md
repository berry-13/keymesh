# KeyMesh Wiring Reference

## USB Connection (Required)

Plug the Pico W into the target server's USB port.
The device appears as a HID keyboard.

## UART Serial Console (Optional)

Connect the Pico W GPIO pins to the target's serial console header:

```
Pico W GPIO 0 (TX)  -->  Target RX
Pico W GPIO 1 (RX)  <--  Target TX
Pico W GND          ---  Target GND
```

Default baud rate: 115200 (configurable in config.json).

## Target Configuration

The target server must have serial console enabled:

- Linux: add `console=ttyS0,115200` to kernel command line
- GRUB: set `GRUB_TERMINAL="serial"` and `GRUB_SERIAL_COMMAND="serial --speed=115200"`
- BIOS/UEFI: enable serial console redirection in firmware settings

## Pin Reference

| Pico W Pin | Function     | Direction |
|------------|--------------|-----------|
| GPIO 0     | UART TX      | Out       |
| GPIO 1     | UART RX      | In        |
| USB        | HID Keyboard | Out       |

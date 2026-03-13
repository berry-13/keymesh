# USB HID keycode mapping for US keyboard layout.
#
# Modifier bitmask (report byte 0):
#   0x01 = Left Ctrl    0x10 = Right Ctrl
#   0x02 = Left Shift   0x20 = Right Shift
#   0x04 = Left Alt     0x40 = Right Alt
#   0x08 = Left GUI     0x80 = Right GUI

MOD_NONE = 0x00
MOD_CTRL = 0x01
MOD_SHIFT = 0x02
MOD_ALT = 0x04
MOD_GUI = 0x08

# Named key constants
KEY_ENTER = 0x28
KEY_ESC = 0x29
KEY_BACKSPACE = 0x2A
KEY_TAB = 0x2B
KEY_SPACE = 0x2C
KEY_DELETE = 0x4C
KEY_RIGHT = 0x4F
KEY_LEFT = 0x50
KEY_DOWN = 0x51
KEY_UP = 0x52
KEY_HOME = 0x4A
KEY_PAGEUP = 0x4B
KEY_END = 0x4D
KEY_PAGEDOWN = 0x4E
KEY_INSERT = 0x49
KEY_CAPSLOCK = 0x39

# F-keys: F1=0x3A .. F12=0x45
KEY_F1 = 0x3A

# Printable ASCII to (keycode, modifier) lookup.
_ASCII_MAP = {}

# a-z
for i in range(26):
    _ASCII_MAP[ord('a') + i] = (0x04 + i, MOD_NONE)

# A-Z
for i in range(26):
    _ASCII_MAP[ord('A') + i] = (0x04 + i, MOD_SHIFT)

# 1-9
for i in range(9):
    _ASCII_MAP[ord('1') + i] = (0x1E + i, MOD_NONE)

# 0
_ASCII_MAP[ord('0')] = (0x27, MOD_NONE)

# Whitespace / control
_ASCII_MAP[ord('\n')] = (KEY_ENTER, MOD_NONE)
_ASCII_MAP[ord('\r')] = (KEY_ENTER, MOD_NONE)
_ASCII_MAP[ord('\t')] = (KEY_TAB, MOD_NONE)
_ASCII_MAP[ord(' ')] = (KEY_SPACE, MOD_NONE)
_ASCII_MAP[0x1B] = (KEY_ESC, MOD_NONE)
_ASCII_MAP[0x7F] = (KEY_BACKSPACE, MOD_NONE)
_ASCII_MAP[0x08] = (KEY_BACKSPACE, MOD_NONE)

# Unshifted symbols
_UNSHIFTED = {
    '-': 0x2D, '=': 0x2E, '[': 0x2F, ']': 0x30,
    '\\': 0x31, ';': 0x33, "'": 0x34, '`': 0x35,
    ',': 0x36, '.': 0x37, '/': 0x38,
}
for ch, kc in _UNSHIFTED.items():
    _ASCII_MAP[ord(ch)] = (kc, MOD_NONE)

# Shifted symbols
_SHIFTED = {
    '!': 0x1E, '@': 0x1F, '#': 0x20, '$': 0x21,
    '%': 0x22, '^': 0x23, '&': 0x24, '*': 0x25,
    '(': 0x26, ')': 0x27, '_': 0x2D, '+': 0x2E,
    '{': 0x2F, '}': 0x30, '|': 0x31, ':': 0x33,
    '"': 0x34, '~': 0x35, '<': 0x36, '>': 0x37,
    '?': 0x38,
}
for ch, kc in _SHIFTED.items():
    _ASCII_MAP[ord(ch)] = (kc, MOD_SHIFT)

# Named special keys (used by WebSocket JSON protocol)
_NAMED_KEYS = {
    "Enter": (KEY_ENTER, MOD_NONE),
    "Tab": (KEY_TAB, MOD_NONE),
    "Backspace": (KEY_BACKSPACE, MOD_NONE),
    "Escape": (KEY_ESC, MOD_NONE),
    "Delete": (KEY_DELETE, MOD_NONE),
    "Insert": (KEY_INSERT, MOD_NONE),
    "Home": (KEY_HOME, MOD_NONE),
    "End": (KEY_END, MOD_NONE),
    "PageUp": (KEY_PAGEUP, MOD_NONE),
    "PageDown": (KEY_PAGEDOWN, MOD_NONE),
    "ArrowUp": (KEY_UP, MOD_NONE),
    "ArrowDown": (KEY_DOWN, MOD_NONE),
    "ArrowLeft": (KEY_LEFT, MOD_NONE),
    "ArrowRight": (KEY_RIGHT, MOD_NONE),
    "CapsLock": (KEY_CAPSLOCK, MOD_NONE),
}
for i in range(12):
    _NAMED_KEYS["F%d" % (i + 1)] = (KEY_F1 + i, MOD_NONE)


def _mod_bits(mod_list):
    bits = 0
    for m in mod_list:
        ml = m.lower()
        if ml == "ctrl":
            bits |= MOD_CTRL
        elif ml == "shift":
            bits |= MOD_SHIFT
        elif ml == "alt":
            bits |= MOD_ALT
        elif ml in ("super", "meta", "gui"):
            bits |= MOD_GUI
    return bits


def char_to_hid(ch):
    c = ord(ch) if isinstance(ch, str) else ch
    return _ASCII_MAP.get(c)


def key_to_hid(name, mod_list=None):
    extra = _mod_bits(mod_list) if mod_list else 0
    entry = _NAMED_KEYS.get(name)
    if entry:
        return (entry[0], entry[1] | extra)
    if len(name) == 1:
        entry = _ASCII_MAP.get(ord(name))
        if entry:
            return (entry[0], entry[1] | extra)
    return None


# VT100 escape sequences for raw TCP mode
_ESC_SEQUENCES = {
    b"[A": (KEY_UP, MOD_NONE),
    b"[B": (KEY_DOWN, MOD_NONE),
    b"[C": (KEY_RIGHT, MOD_NONE),
    b"[D": (KEY_LEFT, MOD_NONE),
    b"[H": (KEY_HOME, MOD_NONE),
    b"[F": (KEY_END, MOD_NONE),
    b"[2~": (KEY_INSERT, MOD_NONE),
    b"[3~": (KEY_DELETE, MOD_NONE),
    b"[5~": (KEY_PAGEUP, MOD_NONE),
    b"[6~": (KEY_PAGEDOWN, MOD_NONE),
    b"OP": (KEY_F1, MOD_NONE),
    b"OQ": (KEY_F1 + 1, MOD_NONE),
    b"OR": (KEY_F1 + 2, MOD_NONE),
    b"OS": (KEY_F1 + 3, MOD_NONE),
    b"[15~": (KEY_F1 + 4, MOD_NONE),
    b"[17~": (KEY_F1 + 5, MOD_NONE),
    b"[18~": (KEY_F1 + 6, MOD_NONE),
    b"[19~": (KEY_F1 + 7, MOD_NONE),
    b"[20~": (KEY_F1 + 8, MOD_NONE),
    b"[21~": (KEY_F1 + 9, MOD_NONE),
    b"[23~": (KEY_F1 + 10, MOD_NONE),
    b"[24~": (KEY_F1 + 11, MOD_NONE),
}


def parse_esc_sequence(buf):
    for seq, hid in _ESC_SEQUENCES.items():
        if buf[:len(seq)] == seq:
            return (hid, len(seq))
    return (None, 0)


def byte_to_hid(b):
    if 0x01 <= b <= 0x1A:
        return (0x04 + b - 1, MOD_CTRL)
    return _ASCII_MAP.get(b)

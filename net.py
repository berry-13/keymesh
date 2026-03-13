import subprocess
import time
import socket


def setup_wifi(config):
    mode = config.get("wifi_mode", "ap")
    if mode == "sta":
        return _setup_sta(config)
    return _setup_ap(config)


def _run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _setup_ap(config):
    ssid = config.get("ap_ssid", "keymesh")
    password = config.get("ap_password", "")
    ip = "192.168.4.1"

    # Stop services that might conflict
    _run(["systemctl", "stop", "wpa_supplicant"])
    _run(["systemctl", "stop", "NetworkManager"])
    _run(["rfkill", "unblock", "wifi"])
    time.sleep(0.5)

    # Configure wlan0 with static IP
    _run(["ip", "addr", "flush", "dev", "wlan0"])
    _run(["ip", "addr", "add", "%s/24" % ip, "dev", "wlan0"])
    _run(["ip", "link", "set", "wlan0", "up"])
    time.sleep(0.5)

    # Write and start hostapd
    hostapd_conf = (
        "interface=wlan0\n"
        "driver=nl80211\n"
        "ssid=%s\n"
        "hw_mode=g\n"
        "channel=7\n"
        "wmm_enabled=0\n"
    ) % ssid
    if password:
        hostapd_conf += (
            "wpa=2\n"
            "wpa_passphrase=%s\n"
            "wpa_key_mgmt=WPA-PSK\n"
            "rsn_pairwise=CCMP\n"
        ) % password

    with open("/tmp/keymesh_hostapd.conf", "w") as f:
        f.write(hostapd_conf)

    _run(["killall", "hostapd"])
    subprocess.Popen(
        ["hostapd", "/tmp/keymesh_hostapd.conf"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    # Write and start dnsmasq for DHCP
    dnsmasq_conf = (
        "interface=wlan0\n"
        "dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h\n"
        "address=/keymesh.local/%s\n"
    ) % ip

    with open("/tmp/keymesh_dnsmasq.conf", "w") as f:
        f.write(dnsmasq_conf)

    _run(["killall", "-9", "dnsmasq"])
    subprocess.Popen(
        ["dnsmasq", "-C", "/tmp/keymesh_dnsmasq.conf", "--no-daemon"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)

    print("AP mode: SSID=%s IP=%s" % (ssid, ip))
    return ip


def _setup_sta(config):
    ssid = config.get("sta_ssid", "")
    password = config.get("sta_password", "")

    if not ssid:
        print("STA: no SSID configured, falling back to AP")
        return _setup_ap(config)

    # Try nmcli first (Bookworm), then wpa_supplicant
    r = _run(["nmcli", "dev", "wifi", "connect", ssid, "password", password])
    if r.returncode != 0:
        # wpa_supplicant fallback
        wpa_conf = 'network={\n  ssid="%s"\n  psk="%s"\n}\n' % (ssid, password)
        with open("/tmp/keymesh_wpa.conf", "w") as f:
            f.write(wpa_conf)
        _run(["wpa_supplicant", "-B", "-i", "wlan0", "-c", "/tmp/keymesh_wpa.conf"])
        _run(["dhclient", "wlan0"])

    # Wait for connection
    for _ in range(15):
        ip = _get_ip()
        if ip and ip != "127.0.0.1":
            print("STA mode: connected to %s at %s" % (ssid, ip))
            return ip
        time.sleep(1)

    print("STA: failed to connect to %s, falling back to AP" % ssid)
    return _setup_ap(config)


def _get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

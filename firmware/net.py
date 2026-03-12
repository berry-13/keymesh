import network
import time


def setup_wifi(config):
    mode = config.get("wifi_mode", "ap")
    if mode == "sta":
        return _setup_sta(config)
    return _setup_ap(config)


def _setup_ap(config):
    wlan = network.WLAN(network.AP_IF)
    wlan.active(True)
    ssid = config.get("ap_ssid", "keymesh")
    password = config.get("ap_password", "")
    if password:
        wlan.config(essid=ssid, password=password, security=4)
    else:
        wlan.config(essid=ssid, security=0)
    # Wait for AP to be active
    while not wlan.active():
        time.sleep(0.1)
    ip = wlan.ifconfig()[0]
    print("AP mode: SSID=%s IP=%s" % (ssid, ip))
    return ip


def _setup_sta(config):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    ssid = config.get("sta_ssid", "")
    password = config.get("sta_password", "")
    if not ssid:
        print("STA mode: no SSID configured, falling back to AP")
        return _setup_ap(config)
    wlan.connect(ssid, password)
    retries = 0
    while not wlan.isconnected() and retries < 20:
        delay = min(1 << (retries // 5), 8)
        time.sleep(delay)
        retries += 1
    if not wlan.isconnected():
        print("STA connection to %s failed, falling back to AP" % ssid)
        wlan.active(False)
        return _setup_ap(config)
    ip = wlan.ifconfig()[0]
    print("STA mode: connected to %s at %s" % (ssid, ip))
    return ip

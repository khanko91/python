"""List devices on the local Wi-Fi network.

Standard library only, so it runs in Termux on Android:
    pkg install python
    python netscan.py

Android blocks apps from reading the ARP table, so devices are found by
probing common TCP ports on every address and listening for SSDP/UPnP
replies (TVs, Chromecasts, speakers, routers announce themselves this way).
"""

import argparse
import ipaddress
import re
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# Port -> hint about what usually listens there.
PROBE_PORTS = {
    80: "web",
    443: "web",
    22: "ssh",
    53: "dns",
    139: "windows/smb",
    445: "windows/smb",
    554: "camera (rtsp)",
    3000: "LG TV",
    3001: "LG TV",
    5000: "airplay/nas",
    7000: "airplay",
    8008: "chromecast/google",
    8009: "chromecast/google",
    8080: "web",
    9080: "chromecast/google",
    62078: "iphone/ipad",
}
LG_TV_PORTS = {3000, 3001}

SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_SEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 2\r\n"
    "ST: ssdp:all\r\n\r\n"
)


def local_ip():
    """Our address on the LAN (no packet is sent by a UDP connect)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def probe(ip, ports, timeout):
    """Return the set of ports that answered (open, or refused = host is up)."""
    answered = set()
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            err = s.connect_ex((ip, port))
        if err == 0:
            answered.add(port)
        elif err in (111, 61, 10061):  # ECONNREFUSED on Linux / macOS / Windows
            answered.add(-port)
    return answered


def parse_ssdp(data):
    """Parse an SSDP reply into a dict of lower-cased header names."""
    headers = {}
    for line in data.decode(errors="replace").split("\r\n")[1:]:
        key, sep, value = line.partition(":")
        if sep:
            headers[key.strip().lower()] = value.strip()
    return headers


def friendly_name(location, timeout=2):
    """Fetch a UPnP device description and pull out <friendlyName>."""
    try:
        with urllib.request.urlopen(location, timeout=timeout) as resp:
            xml = resp.read(65536).decode(errors="replace")
    except Exception:
        return None
    match = re.search(r"<friendlyName>(.*?)</friendlyName>", xml, re.S)
    return match.group(1).strip() if match else None


def ssdp_discover(wait=3):
    """Return {ip: {"server": ..., "location": ...}} for devices that reply."""
    found = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        s.settimeout(wait)
        try:
            s.sendto(SSDP_SEARCH.encode(), SSDP_ADDR)
            while True:
                data, (ip, _) = s.recvfrom(4096)
                headers = parse_ssdp(data)
                entry = found.setdefault(ip, {})
                entry.setdefault("server", headers.get("server"))
                entry.setdefault("location", headers.get("location"))
        except (socket.timeout, OSError):
            pass
    return found


def reverse_dns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


def describe(ip, ports, ssdp, name):
    """Build a one-line guess at what the device is."""
    hints = []
    open_ports = {p for p in ports if p > 0}
    if open_ports & LG_TV_PORTS or "webos" in (ssdp.get("server") or "").lower():
        hints.append("LG webOS TV  <-- use this as --host")
    hints += sorted({PROBE_PORTS[p] for p in open_ports if p not in LG_TV_PORTS})
    if ssdp.get("server") and not hints:
        hints.append(ssdp["server"])
    return name or reverse_dns(ip) or "", ", ".join(dict.fromkeys(hints))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subnet", help="e.g. 192.168.1.0/24 (default: your /24)")
    parser.add_argument("--timeout", type=float, default=0.4, help="per-port seconds")
    args = parser.parse_args(argv)

    me = local_ip()
    subnet = ipaddress.ip_network(args.subnet or f"{me}/24", strict=False)
    hosts = [str(h) for h in subnet.hosts()]
    print(f"This phone: {me}\nScanning {subnet} ({len(hosts)} addresses)...\n")

    with ThreadPoolExecutor(max_workers=64) as pool:
        ssdp_future = pool.submit(ssdp_discover)
        results = dict(zip(hosts, pool.map(lambda ip: probe(ip, PROBE_PORTS, args.timeout), hosts)))
        ssdp = ssdp_future.result()

    alive = sorted(
        {ip for ip, ports in results.items() if ports} | set(ssdp) | {me},
        key=ipaddress.ip_address,
    )
    with ThreadPoolExecutor(max_workers=16) as pool:
        names = dict(zip(alive, pool.map(
            lambda ip: friendly_name(ssdp[ip]["location"]) if ssdp.get(ip, {}).get("location") else None,
            alive,
        )))

    print(f"{'IP':<16} {'NAME':<32} WHAT IT LOOKS LIKE")
    for ip in alive:
        name, hint = describe(ip, results.get(ip, set()), ssdp.get(ip, {}), names[ip])
        if ip == me:
            name, hint = name or "(this phone)", "this phone"
        print(f"{ip:<16} {name[:32]:<32} {hint}")
    print(f"\n{len(alive)} devices found. Phones that are asleep may not show up.")


if __name__ == "__main__":
    main()

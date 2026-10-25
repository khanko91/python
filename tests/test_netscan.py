import socket
import threading

from lgtv.netscan import describe, parse_ssdp, probe


def test_parse_ssdp_headers():
    data = (
        b"HTTP/1.1 200 OK\r\n"
        b"LOCATION: http://192.168.1.20:1234/desc.xml\r\n"
        b"SERVER: WebOS/4.1.0 UPnP/1.0\r\n\r\n"
    )
    headers = parse_ssdp(data)
    assert headers["location"] == "http://192.168.1.20:1234/desc.xml"
    assert headers["server"] == "WebOS/4.1.0 UPnP/1.0"


def test_describe_flags_lg_tv():
    _, hint = describe("192.0.2.9", {3000, 80}, {}, "Living Room TV")
    assert hint.startswith("LG webOS TV")
    assert "web" in hint


def test_describe_flags_lg_tv_from_ssdp_server():
    _, hint = describe("192.0.2.9", set(), {"server": "WebOS/9 UPnP/1.0"}, None)
    assert hint.startswith("LG webOS TV")


def test_probe_detects_open_and_refused_ports():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    open_port = server.getsockname()[1]
    threading.Thread(target=lambda: server.accept(), daemon=True).start()

    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    closed_port = closed.getsockname()[1]
    closed.close()

    answered = probe("127.0.0.1", [open_port, closed_port], timeout=0.5)
    server.close()
    assert open_port in answered
    assert -closed_port in answered

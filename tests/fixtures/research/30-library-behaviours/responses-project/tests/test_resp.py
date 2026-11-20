import hashlib
import socket

import pytest
import requests
import responses

URL = "https://api.github.com/repos/o/r/releases/assets/1"


def _short(**kw):
    responses.add(responses.GET, URL, body=b"abc", headers={"Content-Length": "10"}, **kw)


@responses.activate
def test_short_body_stream():
    _short(auto_calculate_content_length=False)
    r = requests.get(URL, stream=True, timeout=5)
    print("HEADER Content-Length:", r.headers.get("Content-Length"))
    got = b""
    try:
        for chunk in r.iter_content(4):
            got += chunk
        print("STREAM: no error, got", got)
    except Exception as e:
        print("STREAM RAISED:", type(e).__module__ + "." + type(e).__name__, "|", str(e)[:150], "| got", got)


@responses.activate
def test_short_body_content():
    _short(auto_calculate_content_length=False)
    try:
        r = requests.get(URL, timeout=5)
        print("CONTENT: no error, len", len(r.content), r.headers.get("Content-Length"))
    except Exception as e:
        print("CONTENT RAISED:", type(e).__module__ + "." + type(e).__name__, "|", str(e)[:150])


@responses.activate
def test_short_body_raw_read():
    _short(auto_calculate_content_length=False)
    r = requests.get(URL, stream=True, timeout=5)
    try:
        data = r.raw.read(decode_content=True)
        print("RAW READ: no error, len", len(data))
    except Exception as e:
        print("RAW READ RAISED:", type(e).__module__ + "." + type(e).__name__, "|", str(e)[:150])


@responses.activate
def test_mocked_request_with_socket_disabled():
    responses.add(responses.GET, "https://api.github.com/x", json={"ok": True})
    assert requests.get("https://api.github.com/x", timeout=5).json() == {"ok": True}
    print("MOCKED OK under --disable-socket")


@responses.activate
def test_unregistered_url():
    with pytest.raises(requests.exceptions.ConnectionError) as ei:
        requests.get("https://api.github.com/unregistered", timeout=5)
    print("UNREGISTERED:", type(ei.value).__name__, str(ei.value)[:100])


def test_real_request_blocked():
    try:
        requests.get("https://api.github.com/", timeout=5)
        print("REAL: NOT BLOCKED")
    except Exception as e:
        print("REAL BLOCKED:", type(e).__module__ + "." + type(e).__name__, "|", str(e)[:100])


@responses.activate
def test_connection_error_body():
    responses.add(responses.GET, "https://api.github.com/down", body=requests.exceptions.ConnectionError("down"))
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("https://api.github.com/down", timeout=5)
    print("CONNERROR OK")

"""Local fake-server integration tests; never connect to a real Windows host."""
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


class ShutdownTests(unittest.TestCase):
    def check_shutdown(self, terminate):
        connected, disconnected = threading.Event(), threading.Event()
        packets, failures = [], []
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)

        def fake_windows():
            try:
                with listener.accept()[0] as sock:
                    sock.settimeout(5)
                    pending = bytearray()
                    while True:
                        part = sock.recv(4096)
                        if not part:
                            break
                        pending.extend(part)
                        while len(pending) >= 128:
                            kind, length = struct.unpack_from("<II", pending)
                            if len(pending) < 128 + length:
                                break
                            packet = bytes(pending[:128 + length])
                            del pending[:128 + length]
                            packets.append(packet)
                            if kind == 0:
                                connected.set()
                            if kind == 8:
                                disconnected.set()
                                sock.shutdown(socket.SHUT_WR)
                                return
            except Exception as error:
                failures.append(str(error))

        worker = threading.Thread(target=fake_windows, daemon=True)
        worker.start()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env = dict(os.environ, SPACEDESK_DRIVER="127.0.0.1",
                   SPACEDESK_PORT=str(listener.getsockname()[1]),
                   SPACEDESK_HTTP_PORT=str(port), SPACEDESK_AUTORECONNECT="0")
        source = Path(__file__).parents[1] / "src/spacedesk_linux/bridge.py"
        process = subprocess.Popen([sys.executable, "-B", str(source)], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        websocket = None
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=0.1):
                        break
                except (OSError, urllib.error.URLError):
                    if process.poll() is not None:
                        self.fail(process.communicate()[1])
                    time.sleep(0.02)
            else:
                self.fail("bridge HTTP server did not start")
            websocket = socket.create_connection(("127.0.0.1", port), timeout=2)
            websocket.sendall((f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                               "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                               "Sec-WebSocket-Version: 13\r\n\r\n").encode())
            self.assertTrue(connected.wait(3), "driver handshake missing")
            start = time.monotonic()
            if terminate:
                process.terminate()
            else:
                # A masked empty Close frame avoids a TCP reset from unread data.
                websocket.sendall(b"\x88\x80\x00\x00\x00\x00")
            self.assertTrue(disconnected.wait(3), "explicit Disconnect packet missing")
            self.assertLess(time.monotonic() - start, 3)
            worker.join(timeout=1)
            self.assertFalse(failures, failures)
            self.assertEqual(struct.unpack_from("<II", packets[-1]), (8, 0))
            if terminate:
                process.wait(timeout=3)
                self.assertEqual(process.returncode, 0, process.communicate()[1])
        finally:
            if websocket is not None:
                websocket.close()
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            listener.close()
            worker.join(timeout=1)

    def test_sigterm_sends_disconnect_and_exits_without_http_deadlock(self):
        self.check_shutdown(terminate=True)

    def test_last_viewer_close_sends_disconnect(self):
        self.check_shutdown(terminate=False)

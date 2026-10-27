#!/usr/bin/env python3
"""Offline regression checks; never connect to Windows or start services."""
import importlib.util
import struct
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, call


def load_client():
    spec = importlib.util.spec_from_file_location(
        "client_under_test", Path(__file__).parents[1] / "src/spacedesk_linux/bridge.py"
    )
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    return client


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = load_client()

    def test_identification_is_one_complete_string(self):
        client = self.client
        identities = []
        for number in (1, 2):
            client.DEVICE_NAME = f"Linux-monitor-{number}"
            packet = client.build_handshake()
            self.assertEqual(len(packet), 462)
            self.assertEqual(struct.unpack_from("<I", packet, 4)[0], 334)
            identity = packet[128:].decode("utf-16-le").split("\0", 1)[0]
            self.assertTrue(identity.startswith("{"))
            self.assertTrue(identity.endswith(" " + client.DEVICE_NAME))
            self.assertNotIn("\x01", identity)
            self.assertEqual(packet, client.build_handshake())
            identities.append(identity)
        self.assertNotEqual(*identities)

    def test_identification_rejects_overlong_names(self):
        self.client.DEVICE_NAME = "x" * 200
        with self.assertRaises(ValueError):
            self.client.build_handshake()

    def test_pong_uses_response_flag(self):
        pong = self.client.build_pong()
        self.assertEqual(len(pong), 128)
        self.assertEqual(struct.unpack_from("<I", pong)[0], 1)
        self.assertEqual(struct.unpack_from("<I", pong, 12)[0], 2)

    def test_disconnect_packet_has_type_eight_and_no_payload(self):
        packet = self.client.build_disconnect()
        self.assertEqual(len(packet), 128)
        self.assertEqual(struct.unpack_from("<II", packet), (8, 0))
        self.assertEqual(packet[8:], bytes(120))

    def test_intentional_close_notifies_windows_before_socket_shutdown(self):
        client = self.client
        sock = Mock()
        sock.recv.return_value = b""
        client.driver_sock = sock
        with patch.object(client, "set_status"), patch.object(client, "log"):
            client._close_driver_connection()
        expected = [call.settimeout(0.75), call.sendall(client.build_disconnect()),
                    call.shutdown(client.socket.SHUT_WR)]
        self.assertEqual(sock.mock_calls[:3], expected)
        sock.close.assert_called_once_with()
        self.assertIsNone(client.driver_sock)
        sock.reset_mock()
        client._close_driver_connection()
        sock.sendall.assert_not_called()

    def test_close_finishes_even_if_disconnect_write_fails(self):
        client = self.client
        sock = Mock()
        sock.sendall.side_effect = TimeoutError("server unavailable")
        client.driver_sock = sock
        with patch.object(client, "set_status"), patch.object(client, "log"):
            client._close_driver_connection()
        sock.close.assert_called_once_with()
        self.assertIsNone(client.driver_sock)
        self.assertTrue(client._send_lock.acquire(blocking=False))
        client._send_lock.release()

    def test_stopping_bridge_cannot_reconnect(self):
        client = self.client
        client._stopping.set()
        with patch.object(client.socket, "socket") as create:
            client._open_driver_connection()
        create.assert_not_called()

    def test_http_rejects_cross_origin_access(self):
        handler = object.__new__(self.client.Handler)
        handler.headers = {"Host": "127.0.0.1:8091", "Origin": "https://untrusted.example"}
        handler.send_error = Mock()
        with patch.object(self.client, "HTTP_PORT", 8091):
            self.assertFalse(handler._local_request())
        handler.send_error.assert_called_once()

    def test_http_rejects_rebinding_host(self):
        handler = object.__new__(self.client.Handler)
        handler.headers = {"Host": "untrusted.example:8091"}
        handler.send_error = Mock()
        with patch.object(self.client, "HTTP_PORT", 8091):
            self.assertFalse(handler._local_request())

    def test_http_allows_local_browser_and_cli(self):
        for origin in (None, "http://127.0.0.1:8091"):
            handler = object.__new__(self.client.Handler)
            handler.headers = {"Host": "127.0.0.1:8091"}
            if origin:
                handler.headers["Origin"] = origin
            with patch.object(self.client, "HTTP_PORT", 8091):
                self.assertTrue(handler._local_request())

    def test_four_video_fragments_get_one_ack(self):
        client = self.client
        client.MAX_FPS = 0
        sock = Mock()
        client.driver_sock = sock
        packets = []
        for top in (0, 270, 540, 810):
            header = bytearray(128)
            struct.pack_into("<IIII", header, 0, 2, 4, 1920, 1080)
            struct.pack_into("<IIII", header, 24, 0, top, 1920, top + 270)
            struct.pack_into("<I", header, 64, 1)
            packets.extend((bytes(header), b"\xff\xd8\xff\xd9"))
        packets.append(ConnectionError("end of test"))
        with patch.object(client, "_recv_exact", side_effect=packets), \
                patch.object(client, "_broadcast_tile"), patch.object(client, "set_status"), \
                patch.object(client, "log"):
            client.recv_loop(sock, 0)
        sock.sendall.assert_called_once_with(client.FLOW_ACK)
        self.assertEqual(client.connection_status["tiles"], 4)

    def test_ack_does_not_reach_new_connection(self):
        client = self.client
        old, current = Mock(), Mock()
        client.driver_sock = current
        client.send_packet(client.FLOW_ACK, old)
        current.sendall.assert_not_called()
        old.sendall.assert_not_called()

    def test_new_viewer_can_retry_a_dead_driver_with_old_window_present(self):
        client = self.client
        client.client_count = 1
        with patch.object(client, "_open_driver_connection") as connect:
            client.client_join()
        connect.assert_called_once_with()
        self.assertEqual(client.client_count, 2)

    def test_launcher_import_has_no_side_effects(self):
        spec = importlib.util.spec_from_file_location(
            "launcher_under_test", Path(__file__).parents[1] / "docs/legacy-launch.py"
        )
        launcher = importlib.util.module_from_spec(spec)
        with patch("subprocess.run") as run, patch("subprocess.Popen") as popen:
            spec.loader.exec_module(launcher)
        run.assert_not_called()
        popen.assert_not_called()

    def test_opening_a_streaming_viewer_does_not_duplicate_browser(self):
        spec = importlib.util.spec_from_file_location(
            "launcher_under_test", Path(__file__).parents[1] / "docs/legacy-launch.py"
        )
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with patch.object(launcher, "browser_pids", return_value=[123]), \
                patch.object(launcher, "status", return_value={"state": "streaming"}), \
                patch.object(launcher, "place_window") as place, \
                patch.object(launcher.subprocess, "run"), \
                patch.object(launcher.subprocess, "Popen") as popen, \
                patch.object(launcher.urllib.request, "urlopen"):
            launcher.open_monitor(1)
        popen.assert_not_called()
        place.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()

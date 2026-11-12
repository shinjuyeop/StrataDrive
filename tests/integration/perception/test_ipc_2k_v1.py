import socket
import struct
import unittest
from dataclasses import replace

from physical_ai.perception.async_native_2k_v1 import NativeDetection, NativeResult
from physical_ai.perception.boundary_2k_v1 import BoundaryObservation, Publication
from physical_ai.perception.contract import FrameIdentity
from physical_ai.perception.ipc_2k_v1 import Publisher, encode, socket_pair


class Ipc2kTests(unittest.TestCase):
    def setUp(self):
        self.tx, self.rx = socket_pair()
        self.addCleanup(self.tx.close);self.addCleanup(self.rx.close)
        self.publisher = Publisher(self.tx, 42, 77, 88)
        r = NativeResult(FrameIdentity(42, 77, 5, 50_000_000), (NativeDetection(2, .8, (0, 0, 2560, 1536)),))
        self.obs = BoundaryObservation(Publication(r, 88, 1_000_000_000, 1_100_000_000), 60_000_000, 1_010_000_000, 1_005_000_000)

    def test_canonical_bytes_original_times_and_repeated_poll(self):
        data, disposition = self.publisher.send(self.obs, 6, 1_011_000_000)
        self.assertEqual(disposition, "sent");self.assertEqual(self.rx.recv(6000), data)
        self.assertEqual(len(data), 232);self.assertEqual(data[:8], b"S2KPIPC1")
        self.assertEqual(struct.unpack_from("<I", data, 12)[0], 2)
        self.assertEqual(struct.unpack_from("<5Q", data, 88), (5, 50_000_000, 150_000_000, 1_000_000_000, 1_100_000_000))
        second, disposition = self.publisher.send(self.obs, 6, 1_012_000_000)
        self.assertEqual(len(second), 80);self.assertEqual(struct.unpack_from("<I", second, 12)[0], 1)

    def test_backpressure_does_not_commit_unsent_publication_as_poll(self):
        while True:
            try:self.tx.send(b"x" * 4984)
            except BlockingIOError:break
        data, disposition = self.publisher.send(self.obs, 6, 1_011_000_000)
        self.assertEqual(disposition, "full");self.assertEqual(self.publisher.sent, 0)
        while True:
            try:self.rx.recv(6000)
            except BlockingIOError:break
        data, disposition = self.publisher.send(self.obs, 6, 1_012_000_000)
        self.assertEqual(disposition, "sent");self.assertEqual(struct.unpack_from("<I", data, 12)[0], 2)
        self.assertEqual(self.publisher.dropped, 1)

    def test_unavailable_cannot_republish_old_result(self):
        self.publisher.send(self.obs, 6, 1_011_000_000)
        absent = replace(self.obs, publication=None)
        data, _ = self.publisher.send(absent, 6, 1_012_000_000)
        self.assertEqual(struct.unpack_from("<I", data, 12)[0], 0)
        data, _ = self.publisher.send(self.obs, 6, 1_013_000_000)
        self.assertEqual(struct.unpack_from("<I", data, 12)[0], 1)

    def test_no_state_is_explicit_and_clock_identity_cannot_change(self):
        absent = replace(self.obs, publication=None, source_ns=None)
        data, _ = self.publisher.send(absent, 0, 1_011_000_000)
        self.assertEqual(struct.unpack_from("<3Q", data, 56), (0, 0, 0))
        with self.assertRaises(ValueError):
            encode(self.obs, sequence=1, epoch=43, source_clock=77, wall_clock=88, state_frame=6, sender_wall_ns=1_011_000_000)
        with self.assertRaises(ValueError):
            self.publisher.send(replace(self.obs, source_ns=None), 0, 1_011_000_000)

    def test_disconnect_is_recorded_without_signal_or_wait(self):
        self.rx.close()
        _, disposition = self.publisher.send(self.obs, 6, 1_011_000_000)
        self.assertEqual(disposition, "disconnected");self.assertTrue(self.publisher.closed)
        self.assertEqual(self.publisher.dropped, 1)

    def test_blocking_or_stream_socket_is_not_accepted(self):
        self.tx.setblocking(True)
        with self.assertRaises(ValueError):Publisher(self.tx, 42, 77, 88)
        a, b = socket.socketpair()
        self.addCleanup(a.close);self.addCleanup(b.close);a.setblocking(False)
        with self.assertRaises(ValueError):Publisher(a, 42, 77, 88)


if __name__ == "__main__":
    unittest.main()

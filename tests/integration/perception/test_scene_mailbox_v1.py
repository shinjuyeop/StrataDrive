from dataclasses import FrozenInstanceError, replace
import multiprocessing
import socket
import struct
import unittest

from physical_ai.perception.scene_mailbox_v1 import (
    ACK, ACTOR, HEADER, MAX_BYTES, ActorPose, SceneBinding, SceneSnapshot,
    ScenePublisher, SceneConsumer, encode, decode, socket_pair,
)
from physical_ai.perception.ipc_2k_v1 import encode as encode_perception

BINDING=SceneBinding(42,bytes(range(16)),77,1,5_000_000,b's'*32,b'm'*32,(86,))
BASE=1_000_000_000


def sample(frame):
    return SceneSnapshot(BINDING,frame,frame*5_000_000,BASE+frame*1000,BASE+frame*1000+1,
                         (ActorPose(86,(frame*.01,2.,3.),(0.,0.,0.,1.),(1.,0.,0.),(0.,0.,0.)),))


def stalled_process(sock,unused,taken,release,result):
    unused.close();consumer=SceneConsumer(sock,BINDING)
    first=consumer.take(BASE+2000)
    result.put(first.frame);taken.set()
    if not release.wait(3):return
    consumer.release();consumer.close()


class SceneMailboxTests(unittest.TestCase):
    def pair(self):
        a,b=socket_pair();publisher=ScenePublisher(a,BINDING);consumer=SceneConsumer(b,BINDING)
        self.addCleanup(publisher.close);self.addCleanup(consumer.close)
        return publisher,consumer

    def test_exact_roundtrip_complete_inventory_and_immutable_kinematics(self):
        value=sample(1);self.assertEqual(decode(encode(value),BINDING),value)
        with self.assertRaises(FrozenInstanceError):value.frame=2
        with self.assertRaises(ValueError):replace(value,actors=())
        with self.assertRaises(ValueError):replace(value.actors[0],position_m=[0,0,0])
        with self.assertRaises(ValueError):replace(value.actors[0],position_m=(float('nan'),0,0))
        with self.assertRaises(ValueError):replace(value.actors[0],quaternion_xyzw=(0,0,0,0))
        with self.assertRaises(ValueError):replace(BINDING,actor_ids=(86,86))

    def test_stall_holds_one_active_and_replaces_only_one_pending(self):
        publisher,consumer=self.pair();first=sample(1)
        self.assertTrue(publisher.offer(first,first.acquired_end_ns))
        self.assertEqual(consumer.take(first.acquired_end_ns),first)
        for i in range(2,101):
            value=sample(i);self.assertTrue(publisher.offer(value,value.acquired_end_ns))
        self.assertEqual((publisher.sent,publisher.inflight,publisher.pending.frame,publisher.replaced),(1,1,100,98))
        self.assertEqual(consumer.current(sample(100).acquired_end_ns),first)
        consumer.release();publisher.pump(sample(100).acquired_end_ns)
        self.assertEqual(consumer.take(sample(100).acquired_end_ns),sample(100))
        self.assertEqual(publisher.sent,2)

    def test_exact_scene_age_expires_without_renewing_acquisition(self):
        publisher,consumer=self.pair();value=sample(1)
        publisher.offer(value,value.acquired_end_ns)
        consumer.take(value.acquired_end_ns)
        self.assertEqual(consumer.current(value.acquired_begin_ns+99_999_999),value)
        self.assertIsNone(consumer.current(value.acquired_begin_ns+100_000_000))
        self.assertEqual(consumer.expired,1)
        publisher.pump(value.acquired_begin_ns+100_000_000)
        self.assertEqual(publisher.inflight,0)

    def test_stale_inflight_and_pending_are_dropped_after_pause(self):
        publisher,consumer=self.pair();one,two=sample(1),sample(2)
        publisher.offer(one,one.acquired_end_ns);publisher.offer(two,two.acquired_end_ns)
        now=two.acquired_begin_ns+100_000_000
        self.assertIsNone(consumer.take(now));publisher.pump(now)
        self.assertIsNone(publisher.pending);self.assertEqual(publisher.expired,1)
        self.assertEqual(consumer.expired,1);self.assertEqual(publisher.sent,1)

    def test_session_configuration_period_and_wire_corruption_rejected(self):
        for binding in (replace(BINDING,epoch=43),replace(BINDING,world=78),replace(BINDING,generation=2),
                        replace(BINDING,step_ns=10_000_000),replace(BINDING,scene_sha256=b'x'*32),replace(BINDING,actor_ids=(87,))):
            with self.subTest(binding=binding),self.assertRaises(ValueError):decode(encode(sample(1)),binding)
        data=encode(sample(1))
        for bad in (data[:-1],data+b'x',b'x'+data[1:]):
            with self.assertRaises(ValueError):decode(bad,BINDING)
        bad=bytearray(data);struct.pack_into('<d',bad,HEADER.size+8,float('inf'))
        with self.assertRaises(ValueError):decode(bad,BINDING)

    def test_producer_rejects_future_and_regressing_original_time(self):
        for bad in (sample(1),replace(sample(2),source_ns=5_000_000),replace(sample(2),acquired_begin_ns=BASE+1001)):
            publisher,consumer=self.pair();publisher.offer(sample(1),sample(1).acquired_end_ns)
            with self.assertRaises(ValueError):publisher.offer(bad,sample(2).acquired_end_ns)
            self.assertTrue(publisher.closed)
        publisher,consumer=self.pair()
        with self.assertRaises(ValueError):publisher.offer(sample(1),sample(1).acquired_end_ns-1)
        self.assertTrue(publisher.closed)

    def test_receiver_rejects_source_regression_and_bad_ack_closes_publisher(self):
        a,b=socket_pair();consumer=SceneConsumer(b,BINDING);self.addCleanup(a.close);self.addCleanup(consumer.close)
        a.send(encode(sample(1)));consumer.take(sample(1).acquired_end_ns);consumer.release();a.recv(ACK.size)
        a.send(encode(replace(sample(2),source_ns=5_000_000)))
        with self.assertRaises(ValueError):consumer.take(sample(2).acquired_end_ns)
        self.assertTrue(consumer.closed)
        publisher,peer=self.pair();publisher.offer(sample(1),sample(1).acquired_end_ns)
        peer.sock.send(ACK.pack(b'SDSCACK1',999))
        with self.assertRaises(ValueError):publisher.pump(sample(2).acquired_end_ns)
        self.assertTrue(publisher.closed)

    def test_real_process_stall_does_not_make_producer_wait_for_consumer(self):
        context=multiprocessing.get_context('fork');a,b=socket_pair()
        publisher=ScenePublisher(a,BINDING);publisher.offer(sample(1),sample(1).acquired_end_ns)
        taken,release=context.Event(),context.Event();result=context.Queue()
        process=context.Process(target=stalled_process,args=(b,a,taken,release,result));process.start();b.close()
        try:
            self.assertTrue(taken.wait(2));self.assertEqual(result.get(timeout=2),1)
            for i in range(2,101):publisher.offer(sample(i),sample(i).acquired_end_ns)
            self.assertTrue(process.is_alive());self.assertEqual(publisher.sent,1)
            self.assertEqual(publisher.pending.frame,100)
            self.assertEqual(publisher.replaced,98)
        finally:
            release.set();process.join(3)
            if process.is_alive():process.terminate();process.join(2)
            publisher.close();result.close()
        self.assertEqual(process.exitcode,0)

    def test_disconnect_and_clock_regression_clear_consumer_availability(self):
        publisher,consumer=self.pair();publisher.close()
        self.assertIsNone(consumer.take(BASE));self.assertTrue(consumer.closed)
        publisher,consumer=self.pair();publisher.offer(sample(1),sample(1).acquired_end_ns)
        consumer.take(sample(1).acquired_end_ns);publisher.close()
        self.assertIsNone(consumer.current(sample(1).acquired_end_ns));self.assertTrue(consumer.closed)
        publisher,consumer=self.pair();publisher.offer(sample(1),sample(1).acquired_end_ns)
        consumer.take(sample(1).acquired_end_ns)
        with self.assertRaises(ValueError):consumer.current(BASE)
        self.assertTrue(consumer.closed);self.assertIsNone(consumer.active)

    def test_scene_is_not_a_perception_publication_and_endpoint_is_bounded(self):
        with self.assertRaises(ValueError):encode_perception(sample(1),sequence=1,epoch=42,source_clock=77,wall_clock=9,state_frame=1,sender_wall_ns=BASE)
        self.assertLess(MAX_BYTES,16384)
        a,b=socket.socketpair()
        try:
            a.setblocking(False)
            with self.assertRaises(ValueError):ScenePublisher(a,BINDING)
        finally:a.close();b.close()


if __name__=='__main__':unittest.main()

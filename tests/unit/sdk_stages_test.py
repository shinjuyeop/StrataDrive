"""Timestamp and correlation mutation tests; no SDK or network privilege needed."""
import copy
import csv
import json
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tests/integration/someip'),str(ROOT/'tests/integration/diagnostics')]
import kernel_capture as kernel
import audit_sdk_stages as audit
import audit_service_timing as timing
import front_run


class SdkIoThreadTest(unittest.TestCase):
    def test_explicit_configuration_preserves_other_sdk_settings(self):
        with mock.patch.dict(os.environ,{'STRATADRIVE_SDK_IO_THREADS':'2'}):
            old=front_run.config('central',2,True)
        with mock.patch.dict(os.environ,{'STRATADRIVE_SDK_IO_THREADS':'1'}):
            new=front_run.config('central',2,True)
        self.assertEqual(new['applications'][0]['threads'],1)
        new['applications'][0]['threads']=2;self.assertEqual(new,old)

    def test_independent_actual_thread_count_and_policy(self):
        threads=[{'name':'1312_io 0','tid':100,'affinity':[4],'policy':0,'priority':0},
                 {'name':'1312_m_dispatch','tid':101,'affinity':[4],'policy':0,'priority':0}]
        timing.io_threads(threads,1,4)
        with self.assertRaises(ValueError):timing.io_threads(threads,2,4)
        for field,value in [('affinity',[1]),('policy',1),('priority',1)]:
            changed=copy.deepcopy(threads);changed[0][field]=value
            with self.assertRaises(ValueError):timing.io_threads(changed,1,4)

    def test_fifo_is_explicit_and_cannot_accept_wrong_priority_or_cpu(self):
        threads=[{'name':'1312_io 0','tid':100,'affinity':[4],'policy':1,'priority':1}]
        timing.io_threads(threads,1,4,True)
        with self.assertRaises(ValueError):timing.io_threads(threads,1,4)
        for field,value in [('affinity',[1]),('policy',0),('policy',2),('priority',0),('priority',2)]:
            changed=copy.deepcopy(threads);changed[0][field]=value
            with self.assertRaises(ValueError):timing.io_threads(changed,1,4,True)


class KernelTimestampTest(unittest.TestCase):
    def test_timestamp_is_kernel_ancillary_not_read_clock(self):
        ancillary=[(socket.SOL_SOCKET,kernel.TIMESTAMPNS_NEW,struct.pack('=qq',1700000000,987654321))]
        self.assertEqual(kernel.timestamp(ancillary,0),1700000000987654321)
        for data,flags in [([],0),(ancillary*2,0),(ancillary,socket.MSG_CTRUNC),(ancillary,socket.MSG_TRUNC),
                           ([(socket.SOL_SOCKET,64,b'cut')],0),
                           ([(socket.SOL_SOCKET,64,struct.pack('=qq',1,10**9))],0)]:
            with self.assertRaises(ValueError):kernel.timestamp(data,flags)

    def test_clock_uncertainty_and_backward_bracket_rejected(self):
        row={'mono_before_ns':1000,'mono_after_ns':1020,'wall_ns':2000,'kernel_wall_ns':1500}
        self.assertEqual(audit.clock_bounds([row]),(980,1000))
        for changed in [{**row,'mono_after_ns':999},{**row,'mono_after_ns':102001}]:
            with self.assertRaises(ValueError):audit.clock_bounds([changed])


class StageChainTest(unittest.TestCase):
    def setUp(self):
        self.events={stage:{'ns':1000+i*100,'cpu_ns':100+i*10,'voluntary':0,'involuntary':0,
                            'tid':1 if i<2 else 2 if i<4 else 3} for i,stage in enumerate(audit.STAGES)}

    def test_separate_io_and_callback_cpu_clocks(self):
        self.events['handler-enter']['cpu_ns']=1;self.events['handler-exit']['cpu_ns']=21
        result=audit.stage_chain(self.events)
        self.assertEqual(result['dispatch_wait_ns'],100)
        self.assertEqual(result['tcp_cpu_ns'],10);self.assertEqual(result['enqueue_cpu_ns'],10)
        self.assertEqual(result['handler_cpu_ns'],20)

    def test_missing_stage_order_thread_and_counters(self):
        cases=[]
        missing=copy.deepcopy(self.events);del missing['handler-queued'];cases.append(missing)
        for stage,field,value in [('handler-enter','ns',0),('handler-exit','tid',4),
                                 ('app-message','tid',1),('handler-exit','cpu_ns',0)]:
            changed=copy.deepcopy(self.events);changed[stage][field]=value;cases.append(changed)
        for changed in cases:
            with self.assertRaises(ValueError):audit.stage_chain(changed)


class PacketAssemblyTest(unittest.TestCase):
    def build(self,root,mutation=None):
        raw=b'SDRV\x01\0\0\0'+bytes(range(12));raw+=struct.pack('<I',audit.crc32c(raw))
        message=struct.pack('!HHIHHBBBB',0x534a,0x70,len(raw)+8,0x1522,1,1,1,1,0)+raw
        def frame(seq,payload=b'',flags=0x18):
            ip=bytearray(20);ip[0]=0x45;ip[2:4]=struct.pack('!H',40+len(payload));ip[9]=6
            ip[12:16]=socket.inet_aton('10.88.0.3');ip[16:20]=socket.inet_aton('10.88.0.1')
            tcp=bytearray(20);struct.pack_into('!HHI',tcp,0,40001,30507,seq);tcp[12]=0x50;tcp[13]=flags
            return bytes(12)+b'\x08\x00'+ip+tcp+payload
        packets=[frame(100,flags=2),frame(121,message[20:]),frame(101,message[:20]),frame(121,message[20:])]
        if mutation=='conflict':packets[-1]=packets[-1][:-1]+bytes([packets[-1][-1]^1])
        if mutation=='missing':packets.pop(2)
        if mutation=='crc':packets[2]=packets[2][:-1]+bytes([packets[2][-1]^1])
        rows=[];pcap=bytearray(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1))
        for i,packet in enumerate(packets,1):
            stamp=10**9+i*1000
            rows.append(dict(frame=i,kernel_wall_ns=stamp,mono_before_ns=1000000,wall_ns=1001000000,
                             mono_after_ns=1000020,packet_type=0,bytes=len(packet)))
            pcap+=struct.pack('<IIII',stamp//10**9,(stamp//1000)%10**6,len(packet),len(packet))+packet
        (root/'traffic.pcap').write_bytes(pcap)
        meta={'timestamp_source':'SO_TIMESTAMPNS_NEW','normal_exit':True,'socket_drops':int(mutation=='drop'),'rows':len(rows)}
        (root/'capture.json').write_text(json.dumps(meta))
        if mutation=='timestamp':rows[1]['kernel_wall_ns']+=1000
        with (root/'packet-times.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)

    def test_fragment_reorder_and_retransmission_preserve_first_complete_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.build(root);messages,calibration=audit.capture(root)
            self.assertEqual(len(messages),1);self.assertEqual(messages[0]['kernel_low_ns'],3000)
            self.assertEqual(messages[0]['kernel_high_ns'],3020);self.assertEqual(calibration['uncertainty_ns'],20)

    def test_missing_conflicting_altered_bytes_timestamp_and_drops_rejected(self):
        for mutation in ('conflict','missing','crc','timestamp','drop'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.build(root,mutation)
                with self.assertRaises(ValueError):audit.capture(root)


if __name__=='__main__':unittest.main()

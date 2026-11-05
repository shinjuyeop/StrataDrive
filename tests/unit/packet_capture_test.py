"""Capture writes original bytes and reports a kernel loss even after clean stop."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]/'integration/someip';sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('capture_api',HERE/'run.py');api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)


class PacketCapture(unittest.TestCase):
    def capture(self,drops):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        frame=bytearray(58);frame[12:14]=b'\x08\x00';frame[14]=0x45;frame[16:18]=struct.pack('!H',44);frame[23]=6
        frame[26:30]=bytes((10,88,0,1));frame[30:34]=bytes((10,88,0,2));frame[34:38]=struct.pack('!HH',30501,40000);frame[46]=0x50;frame[54:]=b'test'
        handler={}
        class Socket:
            reads=0;stats=0
            def setsockopt(self,*args):pass
            def getsockopt(self,level,option,*args):
                if level==socket.SOL_SOCKET:return 425984
                self.stats+=1;return struct.pack('=II',10,drops if self.stats>1 else 0)
            def bind(self,*args):pass
            def settimeout(self,*args):pass
            def close(self):pass
            def recv(self,*args):
                self.reads+=1
                if self.reads==1:return bytes(frame)
                handler[signal.SIGINT]();raise socket.timeout()
        with patch.dict(os.environ,{'STRATADRIVE_DIAGNOSTIC_SERVICE':'1'}),patch.object(api.socket,'socket',return_value=Socket()),patch.object(api.signal,'signal',side_effect=lambda n,f:handler.__setitem__(n,f)),patch.object(api.os,'sched_getaffinity',return_value={0}):
            if drops:
                with self.assertRaises(RuntimeError):api.capture_packets(root)
            else:api.capture_packets(root)
        metadata=json.loads((root/'capture.json').read_text());data=(root/'traffic.pcap').read_bytes()
        self.assertEqual(data[40:],frame);self.assertEqual(struct.unpack_from('<II',data,32),(len(frame),len(frame)))
        self.assertEqual(metadata['buffered_bytes'],16+len(frame));self.assertEqual(metadata['socket_drops'],drops)
        self.assertEqual(metadata['affinity'],[0]);self.assertEqual(metadata['effective_receive_buffer'],425984)
        self.assertTrue(metadata['buffered']);return metadata

    def test_original_packet_and_effective_buffer_are_retained(self):self.capture(0)
    def test_clean_process_exit_does_not_hide_kernel_drops(self):self.capture(1)


if __name__=='__main__':unittest.main()

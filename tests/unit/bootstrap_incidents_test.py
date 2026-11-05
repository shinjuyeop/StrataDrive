import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

SPEC=importlib.util.spec_from_file_location('bootstrap_audit',Path(__file__).resolve().parents[1]/'integration/diagnostics/audit_bootstrap_incidents.py')
audit=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def record(kind=1):
    data=bytearray(320);data[:8]=audit.MAGIC;data[8:11]=bytes([kind,4,1])
    struct.pack_into('<IQQ',data,12,123,100,100 if kind==1 else 110)
    data[32:64]=bytes(range(1,33))
    return checksum(data)


def checksum(data):
    struct.pack_into('<I',data,316,zlib.crc32(data[:316]))
    return data


class BootstrapIncidentAudit(unittest.TestCase):
    def test_record_mutations_with_and_without_repaired_crc(self):
        valid=record(2);self.assertEqual(audit.decode(valid)['application_epoch'],None)
        mutations=[('crc',12,1,False),('kind',8,9,True),('operation',9,0,True),
                   ('role',10,4,True),('reserved',11,1,True),('clock',24,1,True),
                   ('size',64,241,True),('truncated',66,2,True),('padding',310,1,True)]
        for name,offset,value,repair in mutations:
            with self.subTest(name=name):
                data=bytearray(valid);data[offset]=value
                if repair:checksum(data)
                with self.assertRaises(ValueError):audit.decode(data)
        with self.assertRaises(ValueError):audit.decode(valid[:-1])

    def test_interruption_retry_binding_and_pending_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'format').write_bytes(audit.MAGIC)
            start=record();attempt=root/start[32:48].hex();attempt.mkdir();(attempt/'begin').write_bytes(start)
            self.assertEqual(audit.audit(root)['interrupted'],1)
            self.assertFalse(audit.audit(root)['all_succeeded'])
            (attempt/'outcome').write_bytes(record(3))
            self.assertEqual(audit.audit(root)['failed'],1)
            for offset in (9,10,12,16,32,48):
                data=record(2);data[offset]+=1;checksum(data);(attempt/'outcome').write_bytes(data)
                with self.subTest(offset=offset),self.assertRaises(ValueError):audit.audit(root)
            (attempt/'outcome').write_bytes(record(2));self.assertTrue(audit.audit(root)['all_succeeded'])
            (attempt/'outcome.pending').write_bytes(record(2))
            with self.assertRaises(ValueError):audit.audit(root)


if __name__=='__main__':unittest.main()

"""Plain/archive readers must retain every record and fail on corrupt evidence."""
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'integration/carla'))
from evidence_io import integer_csv_rows, json_rows, read_json


class CarlaEvidenceTest(unittest.TestCase):
    def test_plain_and_compressed_records_are_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            payloads={'result.json':'{"source":123}', 'trace.jsonl':'{"seq":1}\n{"seq":2}\n',
                      'native.csv':'now,source\r\n21,12\r\n31,22\r\n'}
            for compressed in (False,True):
                for name,text in payloads.items():
                    path=root/name
                    if compressed:path.unlink();path.with_name(name+'.gz').write_bytes(gzip.compress(text.encode()))
                    else:path.write_bytes(text.encode())
                self.assertEqual(read_json(root/'result.json'),{'source':123})
                self.assertEqual(list(json_rows(root/'trace.jsonl')),[{'seq':1},{'seq':2}])
                self.assertEqual(list(integer_csv_rows(root/'native.csv')),[{'now':21,'source':12},{'now':31,'source':22}])

    def test_truncated_or_blank_jsonl_record_is_not_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.jsonl'
            for tail in ('\n','{"seq":'):
                path.write_text('{"seq":1}\n'+tail)
                stream=json_rows(path);self.assertEqual(next(stream),{'seq':1})
                with self.assertRaises(json.JSONDecodeError):next(stream)

    def test_corrupt_plain_file_cannot_fall_back_to_good_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.json';path.write_text('{')
            Path(str(path)+'.gz').write_bytes(gzip.compress(b'{"status":"PASS"}'))
            with self.assertRaises(json.JSONDecodeError):read_json(path)

    def test_missing_evidence_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):read_json(Path(directory)/'missing.json')


if __name__=='__main__':unittest.main()

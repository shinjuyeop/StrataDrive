import copy
import io
import unittest
from unittest.mock import patch
from audit_watch_timing_v1 import validate
from profile_host_native_v1 import interrupts, read_interrupts


class WatchTimingTests(unittest.TestCase):
    def fixture(self):
        initial=1_000_000_000;horizon=35_000_000_000;first=initial+1_000_000
        meta=dict(first_release_ns=first,last_release_ns=first+horizon,capacity=17501,count=2,overflow=False,
            thread=dict(policy=1,priority=18,allowed_cpus=[1,9],tid=123))
        rows=[];watch=[]
        for i in range(2):
            t=first+i*2_000_000
            r=dict(release_ns=t,sleep_begin_ns=t-500_000,wake_ns=t+10_000,job_end_ns=t+12_000,
                poll_end_ns=t+13_000,grid_now_ns=t+14_000,next_release_ns=t+2_000_000,
                sleep_cpu=1,wake_cpu=1,end_cpu=1,begin_cpu_ns=i*10000,end_cpu_ns=i*10000+3000,
                begin_voluntary=i+1,end_voluntary=i+1,begin_involuntary=0,end_involuntary=0,
                begin_minor_faults=2,end_minor_faults=2,begin_error=0,end_error=0)
            rows.append(r);watch.append(dict(owner=9,release_ns=t,start_ns=r['wake_ns'],end_ns=r['job_end_ns']))
        return meta,rows,watch,initial,horizon

    def test_exact_join_and_mutations(self):
        f=self.fixture();self.assertEqual(validate(*f)['records'],2)
        for key,value in [('wake_ns',1),('job_end_ns',1),('next_release_ns',1),('sleep_cpu',2),
                          ('begin_error',1),('end_cpu_ns',1),('begin_voluntary',0)]:
            meta,rows,watch,initial,horizon=copy.deepcopy(f);rows[1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(meta,rows,watch,initial,horizon)
        meta,rows,watch,initial,horizon=copy.deepcopy(f);watch.append(dict(owner=9,release_ns=initial+5_000_000,start_ns=0,end_ns=0))
        # Missing work remains a physical fault; never manufacture a profile completion.
        self.assertEqual(validate(meta,rows,watch,initial,horizon)['records'],2)
        meta['overflow']=True
        with self.assertRaises(ValueError):validate(meta,rows,watch,initial,horizon)

    def test_interrupt_cpu_columns_and_non_cpu_lines(self):
        result=interrupts(' CPU0 CPU1 CPU2 CPU9\n 9: 1 2 3 4 acpi\n LOC: 5 6 7 8 timer\n ERR: 9\n',[1,9])
        self.assertEqual(result,{'9':dict(counts=[2,4],label='acpi'),'LOC':dict(counts=[6,8],label='timer')})

    def test_interrupt_short_reads_and_fresh_open(self):
        class ShortReads(io.RawIOBase):
            def __init__(self, data):self.data=io.BytesIO(data)
            def readable(self):return True
            def readinto(self, target):
                part=self.data.read(min(7,len(target)));target[:len(part)]=part
                return len(part)
        first=b' CPU1 CPU9\n 9: 1 2 acpi\n LOC: 100 200 timer\n'
        second=first.replace(b'100 200',b'110 220')
        with patch('builtins.open',side_effect=[io.BufferedReader(ShortReads(x)) for x in (first,second)]) as opened:
            self.assertEqual(read_interrupts(),first.decode())
            self.assertEqual(interrupts(read_interrupts(),[1,9])['LOC']['counts'],[110,220])
            self.assertEqual(opened.call_count,2)
        with patch('builtins.open',return_value=io.BufferedReader(ShortReads(first))):
            with self.assertRaisesRegex(ValueError,'truncated'):read_interrupts(limit=8)


if __name__=='__main__':unittest.main()

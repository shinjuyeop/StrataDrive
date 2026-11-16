import copy
import unittest
from audit_host_clock_v1 import CAP,MIN,TURBO,validate


class HostClockTests(unittest.TestCase):
    def fixture(self):
        rows=[]
        for i in range(5):
            values={CAP:70,MIN:16,TURBO:0,'/sys/class/hwmon/hwmon0/temp1_input':65000}
            for cpu in (0,1):
                for counter in ('core_throttle_count','package_throttle_count'):
                    values[f'/sys/devices/system/cpu/cpu{cpu}/thermal_throttle/{counter}']=cpu*100+i
                values[f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq']=800000 if i==2 else 3000000
            rows.append(dict(wall_ns=i*50_000_000,end_ns=i*50_000_000+1000,values=values,errors={}))
        return rows

    def test_per_core_counters_remain_distinct_and_report_low_clocks(self):
        r=validate(self.fixture(),10_000_000,190_000_000,(0,1))
        self.assertEqual(len(r['thermal_delta']),4)
        self.assertEqual(set(r['thermal_delta'].values()),{4})
        self.assertEqual(r['all_cores_at_most_850mhz_wall_ns'],[100_000_000])

    def test_changes_missing_fields_errors_and_gaps_are_rejected(self):
        for mode in ('cap','minimum','turbo','missing','regression','error','order','gap','bracket'):
            with self.subTest(mode=mode):
                rows=copy.deepcopy(self.fixture())
                if mode in ('cap','minimum','turbo'):rows[2]['values'][{'cap':CAP,'minimum':MIN,'turbo':TURBO}[mode]]=100
                if mode=='missing':del rows[2]['values']['/sys/devices/system/cpu/cpu1/thermal_throttle/core_throttle_count']
                if mode=='regression':rows[2]['values']['/sys/devices/system/cpu/cpu1/thermal_throttle/core_throttle_count']=0
                if mode=='error':rows[2]['errors']={'counter':'unavailable'}
                if mode=='order':rows[2]['wall_ns']=0
                if mode=='gap':rows[3]['wall_ns']+=300_000_000;rows[3]['end_ns']+=300_000_000;rows[4]['wall_ns']+=300_000_000;rows[4]['end_ns']+=300_000_000
                if mode=='bracket':rows=rows[1:]
                with self.assertRaises(ValueError):validate(rows,10_000_000,190_000_000,(0,1))


if __name__=='__main__':unittest.main()

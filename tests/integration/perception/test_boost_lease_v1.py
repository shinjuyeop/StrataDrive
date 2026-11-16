import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('m10_boost_lease',Path(__file__).resolve().parents[3]/'tools/m10_boost_lease.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class BoostLeaseTests(unittest.TestCase):
    def fixture(self):
        settings=dict(status='active',min_perf_pct='16',max_perf_pct='100',no_turbo='0')
        events=[];writes=[];elapsed=[0.0]
        def write(name,value):writes.append((name,value));settings[name]=value
        def pause(duration):elapsed[0]+=duration
        kwargs=dict(read=lambda n:settings[n],write=write,owner_alive=lambda:True,stopped=lambda:False,
            seconds=1,clock=lambda:elapsed[0],pause=pause,report=lambda e,**v:events.append((e,v)))
        return settings,events,writes,elapsed,kwargs

    def test_timeout_and_only_one_setting_written(self):
        settings,events,writes,elapsed,kwargs=self.fixture()
        self.assertEqual(module.lease(**kwargs),'TIME_LIMIT')
        self.assertEqual(writes,[('max_perf_pct','70'),('max_perf_pct','100')])
        self.assertEqual(elapsed[0],1);self.assertEqual(events[-1][0],'RESTORED')

    def test_owner_exit_signal_and_exception_restore(self):
        for mode in ('owner','signal','exception'):
            with self.subTest(mode=mode):
                settings,events,writes,elapsed,kwargs=self.fixture()
                if mode=='owner':kwargs['owner_alive']=lambda:elapsed[0]<.5
                if mode=='signal':kwargs['stopped']=lambda:elapsed[0]>=.5
                if mode=='exception':
                    def pause(_):raise OSError('observation failed')
                    kwargs['pause']=pause
                    with self.assertRaises(OSError):module.lease(**kwargs)
                else:self.assertEqual(module.lease(**kwargs),'OWNER_EXIT' if mode=='owner' else 'SIGNAL')
                self.assertEqual(settings['max_perf_pct'],'100')
                self.assertEqual(events[-1][0],'RESTORED')

    def test_external_setting_is_not_overwritten(self):
        settings,events,writes,elapsed,kwargs=self.fixture()
        def pause(_):settings['max_perf_pct']='60'
        kwargs['pause']=pause
        with self.assertRaisesRegex(RuntimeError,'external cap'):module.lease(**kwargs)
        self.assertEqual(settings['max_perf_pct'],'60')
        self.assertEqual(writes,[('max_perf_pct','70')]);self.assertEqual(events[-1][0],'RESTORE_CONFLICT')

    def test_failed_readback_restores_and_no_apply_when_unqualified(self):
        for field,value in [('status','passive'),('max_perf_pct','90'),('min_perf_pct','80'),('no_turbo','1')]:
            settings,events,writes,elapsed,kwargs=self.fixture();settings[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):module.lease(**kwargs)
            self.assertEqual(writes,[])
        settings,events,writes,elapsed,kwargs=self.fixture();kwargs['owner_alive']=lambda:False
        with self.assertRaises(ValueError):module.lease(**kwargs)
        self.assertEqual(writes,[])
        settings,events,writes,elapsed,kwargs=self.fixture();ordinary_read=kwargs['read'];reads=[0]
        def read(name):
            if name=='max_perf_pct':
                reads[0]+=1
                if reads[0]==2:raise OSError('transient read failure')
            return ordinary_read(name)
        kwargs['read']=read
        with self.assertRaises(OSError):module.lease(**kwargs)
        self.assertEqual(settings['max_perf_pct'],'100')


if __name__=='__main__':unittest.main()

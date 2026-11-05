"""Separated gate coverage and causal injected-close classification regressions."""
import copy
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/integration/someip'))
from sdk_outcomes import expected_retired_central_connection, sdk_outcomes
from service_timing_campaign import case_matrix, validate_native_build
spec=importlib.util.spec_from_file_location('sanitizer_suite',ROOT/'tests/integration/diagnostics/service_sanitizer_suite.py')
suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)


class RetiredConnectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.crash=1_000_000_000
        self.line='2026-11-05 13:54:35.498404 front [error] tcei::write_completion_condition: Connection reset by peer(104) bytes transferred: 0 bytes to sent: 85 remote:10.88.0.1:30503 (1422): [5346.0070.01f4]'
        stamp=datetime(2026,11,5,13,54,35,tzinfo=timezone.utc)
        wall=int(stamp.timestamp())*1_000_000_000+498404000
        self.result={'case':'central-rejoin','injected_crash':{'role':'central','generation':1,'ns':self.crash},
                     'central_rejoined':True,'survivor_pids_before':{'front':42,'rear':43},
                     'survivor_pids_after':{'front':42,'rear':43},'forced_cleanup':[],
                     'clock_sample':{'wall_ns':wall,'monotonic_ns':self.crash+10_000_000,'utc_offset_s':0},
                     'processes':[{'role':'central','generation':1,'exit':-9,'expected_abrupt_stop':True},
                                  {'role':'central','generation':2,'exit':1,'summary':{'epoch':3,'release_ack_mask':255}},
                                  *[{'role':p,'generation':1,'exit':0,'summary':{'pass':True,'orderly_stop':True}} for p in ('front','rear')]]}
        for peer,pid in [('front',42),('rear',43)]:
            (self.root/(peer+'.runtime.json')).write_text(json.dumps({'pid':pid}))
            (self.root/(peer+'-protected')).write_text(str(self.crash+20_000_000))
        (self.root/'physical-protected').write_text(str(self.crash+50_000_000))
        self.producer=self.root/'native-diagnostics/central/central-2.producer.json';self.producer.parent.mkdir(parents=True)
        self.producer.write_text(json.dumps({'generation':2,'previous_unclean':True,'boot_ns':self.crash+150_000_000}))

    def classify(self,line=None,result=None,filename='front-1.stdout'):
        return expected_retired_central_connection(line or self.line,filename,result or self.result,self.root)

    def test_first_reset_before_local_protection_is_injected_but_does_not_pass_service(self):
        self.result.update({'pass':False,'sdk_errors':True,'sanitizer_diagnostics':True})
        before=copy.deepcopy(self.result);row=self.classify()
        self.assertEqual(row['event_monotonic_ns'],self.crash+10_000_000)
        self.assertLess(row['event_monotonic_ns'],row['protection_ns']['front'])
        self.assertEqual(self.result,before)

    def test_both_surviving_feedback_routes_and_both_os_errors(self):
        for peer,port,client,service,size in [('front','30503','1422','5346','85'),('rear','30507','1522','534a','117')]:
            line=self.line.replace(' front ',' '+peer+' ').replace('30503',port).replace('1422',client).replace('5346',service).replace('sent: 85','sent: '+size)
            for error in ('Connection reset by peer(104)','Broken pipe(32)'):
                self.assertIsNotNone(self.classify(line.replace('Connection reset by peer(104)',error),filename=peer+'-1.stdout'))

    def test_wrong_connection_generation_payload_or_error_is_unexpected(self):
        for old,new in [('10.88.0.1','10.88.0.2'),('30503','30504'),('1422','1423'),('5346','534a'),
                        ('0070','0080'),('sent: 85','sent: 529'),('sent: 85','sent: 0'),
                        ('Connection reset by peer(104)','Connection refused(111)'),('transferred: 0','transferred: 1')]:
            with self.subTest(new=new):self.assertIsNone(self.classify(self.line.replace(old,new)))
        for name in ('central-1.stdout','front-2.stdout','rear-1.stdout'):self.assertIsNone(self.classify(filename=name))

    def test_missing_crash_rejoin_survivor_release_or_cleanup_cannot_be_excused(self):
        for key,value in [('case','normal'),('central_rejoined',False),('injected_crash',{}),
                          ('forced_cleanup',['rear']),('capture_forced_cleanup',True),('processes',[]),
                          ('survivor_pids_after',{'front':44,'rear':43})]:
            with self.subTest(key=key):self.assertIsNone(self.classify(result=dict(self.result,**{key:value})))
        for index,key,value in [(0,'exit',0),(0,'expected_abrupt_stop',False),(1,'summary',{'epoch':2,'release_ack_mask':127}),
                                (2,'exit',1),(3,'summary',{'pass':False,'orderly_stop':True})]:
            changed=copy.deepcopy(self.result);changed['processes'][index][key]=value
            self.assertIsNone(self.classify(result=changed))
        (self.root/'rear.runtime.json').write_text('{"pid":99}')
        self.assertIsNone(self.classify())

    def test_error_must_be_after_crash_and_strictly_before_successor_boot(self):
        for ns in (self.crash-1,self.crash+150_000_000):
            changed=copy.deepcopy(self.result);changed['clock_sample']['monotonic_ns']=ns
            self.assertIsNone(self.classify(result=changed))
        for key,value in [('generation',1),('previous_unclean',False)]:
            metadata={'generation':2,'previous_unclean':True,'boot_ns':self.crash+150_000_000};metadata[key]=value
            self.producer.write_text(json.dumps(metadata));self.assertIsNone(self.classify())

    def test_original_protection_and_physical_deadlines_still_apply(self):
        for filename in ('front-protected','rear-protected','physical-protected'):
            path=self.root/filename;original=path.read_text()
            for value in (self.crash-1,self.crash+100_000_001):
                path.write_text(str(value));self.assertIsNone(self.classify())
            path.unlink();self.assertIsNone(self.classify());path.write_text(original)

    def test_expected_line_is_retained_and_queue_error_stays_unexpected(self):
        queue='[error] endpoint queue limit exceeded'
        (self.root/'front-1.stdout').write_text(self.line+'\n'+queue+'\n')
        before=(self.root/'front-1.stdout').read_bytes()
        expected,unexpected=sdk_outcomes(self.root,self.result)
        self.assertEqual([r['text'] for r in expected],[self.line]);self.assertEqual([r['text'] for r in unexpected],[queue])
        self.assertEqual((self.root/'front-1.stdout').read_bytes(),before)


class ValidationGateTest(unittest.TestCase):
    def test_native_gate_rejects_instrumented_or_unconfigured_build(self):
        cache='CMAKE_BUILD_TYPE:STRING=RelWithDebInfo\nSTRATADRIVE_SANITIZERS:BOOL=OFF\nSTRATADRIVE_TSAN:BOOL=OFF\nCMAKE_CXX_FLAGS:STRING=-O1 -g\n'
        validate_native_build(cache)
        for bad in ('',cache.replace('RelWithDebInfo','Debug'),cache.replace('SANITIZERS:BOOL=OFF','SANITIZERS:BOOL=ON'),
                    cache.replace('TSAN:BOOL=OFF','TSAN:BOOL=ON'),cache.replace('-O1','-fsanitize=thread')):
            with self.assertRaises(ValueError):validate_native_build(bad)

    def test_split_matrix_is_fixed_eighteen_native_cases(self):
        cases=case_matrix('split-v1');self.assertEqual(len(cases),18);self.assertEqual(len(set(cases)),18)
        self.assertEqual({p for p,_,_,_ in cases},{'normal'})
        for repeat in (1,2,3):
            rows=[(f,d) for _,f,d,r in cases if r==repeat]
            self.assertEqual(rows,[('normal',0),('ack-loss',0),('actual-loss',0),('stop-request-loss',0),('stop-ack-loss',0),('normal',250)])

    def test_legacy_matrix_and_invalid_profile(self):
        self.assertEqual(len(case_matrix('legacy-mixed')),18)
        self.assertEqual(len(case_matrix('legacy-mixed',3)),30)
        with self.assertRaises(ValueError):case_matrix('unknown')
        with self.assertRaises(ValueError):case_matrix('split-v1',3)

    def test_only_wall_suite_moves_to_noninstrumented_gate(self):
        self.assertEqual(len(set(suite.TARGETS)),21)
        self.assertEqual(suite.test_filter('m4_async_runtime_test'),'-M4AsyncWall.*')
        self.assertTrue(all(suite.test_filter(t)=='*' for t in suite.TARGETS if t!='m4_async_runtime_test'))

    def test_no_tests_skips_failures_or_sanitizer_errors_can_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.xml'
            def result(xml,code=0,log=''):
                path.write_text(xml);return suite.judge_xml(path,code,log)['pass']
            valid='<testsuites tests="1" failures="0" errors="0" disabled="0"><testsuite><testcase status="run"/></testsuite></testsuites>'
            self.assertTrue(result(valid))
            for old,new in [('tests="1"','tests="0"'),('failures="0"','failures="1"'),('errors="0"','errors="1"'),('disabled="0"','disabled="1"'),('status="run"','status="notrun"'),('<testcase status="run"/>','<testcase><skipped/></testcase>')]:
                self.assertFalse(result(valid.replace(old,new)))
            self.assertFalse(result(valid,code=1))
            self.assertFalse(result(valid,log='WARNING: ThreadSanitizer: data race'))


if __name__=='__main__':unittest.main()

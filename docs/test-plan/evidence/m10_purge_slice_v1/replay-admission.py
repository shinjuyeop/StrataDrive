"""Post-run gate diagnosis using original native calls, ingress and admissions.

Queries on a 50us grid are counterfactual eligibility probes, not measured polls.
No proof timestamp, receipt, native service time or gate budget is modified.
"""
import argparse
import bisect
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[4]
p = argparse.ArgumentParser()
p.add_argument('--case', required=True)
p.add_argument('--run',type=Path,required=True)
a = p.parse_args()
work = ROOT/'build/m10-purge-slice-v1'/a.case
capture = a.run/'capture'
fault=json.loads((capture/'native-drive-fault.json').read_text());held_frame=fault['held_hv']['sequence']
out = work/'admission-replay'
out.mkdir(exist_ok=False)
events = []
selected = []
def signature(n, kind):
    fields = [n['observed_ns'], n['enable_ns']]
    if kind == 'A':
        fields += [int(n['normal']), n['protection_since_ns'], n['protection_selected_mask'],
                   n['service_mask'], n['credit_mask'], n['release_mask']]
    fields += [x or '-' for x in n['actual']]
    if kind == 'A':
        fields += [x or '-' for key in ('commands', 'release', 'credit') for x in n[key]]
    fields += [n['permission'] or '-']
    return ' '.join(map(str, fields))
with gzip.open(capture/'trace.jsonl.gz', 'rt') as stream:
    for line in stream:
        r = json.loads(line)['receipt']
        n = r['original_actual']['native']; admitted = r['original_actual']['admitted_actual']
        at = int(admitted['command_checked_through_ns'])-5_000_000
        events.append((at, 'A', int(n['observed_ns']), int(r['frame']), signature(n, 'A')))
        if int(r['frame']) in (held_frame, held_frame+1):
            selected.append(r)
ingress_path = capture/'ingress.json'
opener = open if ingress_path.exists() else gzip.open
with opener(ingress_path if ingress_path.exists() else str(ingress_path)+'.gz', 'rt') as stream:
    for row in json.load(stream):
        n = row['ingress']; at = int(n['at_ns'])
        events.append((at, 'I', int(n['observed_ns']), 0, signature(n, 'I')))
assert len(selected) == 2
lo = int(selected[0]['physics_acquisition_end_ns'])
hi = int(selected[1]['physics_acquisition_end_ns'])
paths = list(csv.DictReader((capture/'native-state-path.csv').open()))
published = [int(r['proof_publish_ns']) for r in paths]
for at in range(lo, hi, 50_000):
    row = paths[bisect.bisect_right(published, at)-1]
    events.append((at, 'Q', int(row['service_begin_ns']), 0, '-'))
    events.append((at, 'R', int(row['service_begin_ns']), 0, '-'))
    events.append((at, 'Z', int(row['service_begin_ns']), 0, '-'))
events.sort()
expanded = events
event_file = out/'events.txt'
event_file.write_text(''.join(f'{k} {t} {o} {f} {s}\n' for t,k,o,f,s in expanded))

extra = r'''
#include "native_admission.hpp"
#include <map>
#include <set>
#include <iomanip>
struct Event { char kind; Time at,observed,frame; std::string expected; };
std::string signature(const m7_native::Input& in,char kind) {
    std::ostringstream s;s<<in.observed<<' '<<in.enable;
    if(kind=='A')s<<' '<<in.normal<<' '<<in.protection_since<<' '<<in.protection_selected_mask
        <<' '<<in.service_mask<<' '<<in.credit_mask<<' '<<in.release_mask;
    const auto packet=[&](const m7_native::Packet& p){
        s<<' ';if(!p){s<<'-';return;}
        s<<std::hex<<std::setfill('0');
        for(unsigned i=0;i<p->size;++i)s<<std::setw(2)<<unsigned(p->bytes[i]);
        s<<std::dec;
    };
    for(const auto& p:in.actual)packet(p);
    if(kind=='A') {
        for(const auto& p:in.commands)packet(p);
        for(const auto& p:in.release)packet(p);
        for(const auto& p:in.credit)packet(p);
    }
    packet(in.permission);return s.str();
}
m7_native::Input proof(const Report& r) {
    m7_native::Input in;
    if(r.native_export) {
        const auto& e=*r.native_export;in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;
        in.protection_since=e.protection_since;in.protection_selected_mask=e.protection_selected_mask;
        in.actual=e.actual;in.commands=e.commands;in.release=e.release;in.credit=e.credit;in.permission=e.permission;
    }
    in.service_mask=r.service_mask;in.credit_mask=r.credit_mask;in.release_mask=r.release_mask;return in;
}
'''
source_path=ROOT/'tests/integration/carla/m7_1g/wall_startup_replay.cpp'
frozen=json.loads((ROOT/'docs/test-plan/evidence/m10_purge_slice_v1/sources.json').read_text())
assert hashlib.sha256(source_path.read_bytes()).hexdigest()==frozen['files'][str(source_path.relative_to(ROOT))]['sha256']
source=source_path.read_text()
def replace(old, new):
    global source
    assert source.count(old)==1, old
    source = source.replace(old, new)
replace('int main(int argc,char** argv) {', extra+'\nint main(int argc,char** argv) {')
replace('if(argc!=4 && argc!=5 && argc!=6)', 'if(argc!=7)')
replace('if(argc==6) {', 'if(argc>=6) {')
replace('WallRig rig({1,42,7},actor,initial,model,step,30*ms,endurance);', '''
        WallRig rig({1,42,7},actor,initial,model,step,30*ms,endurance);
        std::vector<Event> events;std::set<Time> needed;std::map<Time,m7_native::Input> proofs;
        std::ifstream event_file(argv[6]);Event e;
        while(event_file>>e.kind>>e.at>>e.observed>>e.frame) {
            std::getline(event_file,e.expected);e.expected.erase(0,1);
            events.push_back(e);needed.insert(e.observed);
        }
        if(!event_file.eof())throw std::runtime_error("events parse");''')
replace('r=rig.service(now,receipt);++calls;const auto& n=r.native;', '''
            r=rig.service(now,receipt);++calls;const auto& n=r.native;
            if(needed.count(now))proofs.emplace(now,proof(n));''')
replace('if(!input.eof())throw std::runtime_error("replay parse");', '''
        if(!input.eof())throw std::runtime_error("replay parse");
        m7_native::Admission gate(42,initial,m7_native::ClockPolicy::HostMonotonic,step);
        std::ofstream diagnoses(std::string(argv[3])+"-admission.csv");
        std::ofstream snapshots(std::string(argv[3])+"-query-proofs.txt");std::set<Time> seen;
        diagnoses<<"kind,at,observed,frame,accepted,reason,oldest,expiry\\n";
        for(const auto& e:events) {
            const auto& in=proofs.at(e.observed);m7_native::Output value;std::string why;bool ok;
            if(e.kind=='Q' && seen.insert(e.observed).second)snapshots<<signature(in,'A')<<'\\n';
            if((e.kind=='A' || e.kind=='I') && signature(in,e.kind)!=e.expected)
                throw std::runtime_error("original proof mismatch "+std::to_string(e.at));
            if(e.kind=='I')ok=gate.ingest(in,e.at);
            else if(e.kind=='A')ok=gate.accept(in,e.at,value);
            else ok=gate.eligible(in,e.at,value,&why,e.kind=='Q'?2000000:(e.kind=='R'?1000000:0));
            if(e.kind=='A' || e.kind=='I') {
                why=gate.error();if(!ok)throw std::runtime_error("original gate event failed "+why);
            }
            diagnoses<<e.kind<<','<<e.at<<','<<e.observed<<','<<e.frame<<','<<ok<<','<<why
                <<','<<value.oldest_actuator<<','<<value.exclusive_expiry<<'\\n';
        }
        if(!diagnoses)throw std::runtime_error("diagnostic write");''')
generated = out/'replay-admission.cpp'; generated.write_text(source)
build = ROOT/'build/m10-watch-timing-v1/native-postfix'
target = build/'tests/integration/carla/m7_1g'
flags = (target/'CMakeFiles/m7_wall_startup_replay.dir/flags.make').read_text()
includes = shlex.split(next(l.split(' = ',1)[1] for l in flags.splitlines() if l.startswith('CXX_INCLUDES = ')))
link = shlex.split((target/'CMakeFiles/m7_wall_startup_replay.dir/link.txt').read_text())
binary = out/'replay-admission'
command = ['/usr/bin/c++', '-O3', '-DNDEBUG', '-std=c++17', '-Wall', '-Wextra', '-Werror',
           *includes, '-I'+str(ROOT/'tools/carla/m7_nodrive'), '-I'+str(ROOT/'tests/integration/carla/m7_1g'),
           str(generated), '-o', str(binary), *link[link.index('-o')+2:]]
subprocess.run(command, cwd=target, check=True)
scenario = ROOT/'tests/integration/carla/scenarios/m10_endurance_hold_v1.txt'
assert scenario.exists()
prefix = out/'replay'
subprocess.run([str(binary), str(work/'replay/input.txt'), str(scenario), str(prefix), '5', '300', str(event_file)], check=True)
assert (out/'replay.csv').read_bytes() == (work/'replay/replay.csv').read_bytes()
rows = list(csv.DictReader((out/'replay-admission.csv').open()))
queries = [r for r in rows if r['kind'] in ('Q','R','Z')]
report = dict(scope=__doc__, query_kind=dict(Q='counterfactual 2ms extra reserve', R='original 1ms extra reserve',
                                          Z='counterfactual 0ms extra reserve'),
              original_native_replay_exact=True,
              original_proof_bytes_equal=True, original_admissions=sum(r['kind']=='A' for r in rows),
              original_ingress=sum(r['kind']=='I' for r in rows), queries=queries,
              generated_source_sha256=hashlib.sha256(generated.read_bytes()).hexdigest(),
              binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
              event_input_sha256=hashlib.sha256(event_file.read_bytes()).hexdigest())
(ROOT/'docs/test-plan/evidence/m10_purge_slice_v1'/a.case/'admission-replay.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='queries'},indent=2))
for row in queries: print(row)

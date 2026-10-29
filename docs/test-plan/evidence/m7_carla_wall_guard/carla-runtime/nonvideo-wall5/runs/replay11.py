from pathlib import Path
import json,csv,subprocess,shlex
root=Path('/d/shin/StrataDrive');work=Path('/d/shin/stratadrive-tools/m7-source/m7-wall-stabilize');d=work/'run11'
r=json.loads((d/'result.json').read_text());meta=json.loads((d/'native.json').read_text());model=int(r['binding']['logical_begin_ns'])
rows={int(x['receipt']['work_end_ns']):x for x in (json.loads(l) for l in (d/'trace.jsonl').read_text().splitlines())}
with (work/'replay11-input.txt').open('w') as f:
 print(meta['initial'],model,r['binding']['actor'],file=f);prev=model
 for n in csv.DictReader((d/'native.csv').open()):
  end=int(n['energy_end']);new=end in rows and end!=prev;print(n['now'],int(new),file=f)
  if new:
   x=rows[end];v=x['receipt'];a=v['original_actual']['admitted_actual'];s=v['solver_work'];p=x['physics']
   vals=[v['frame'],v['logical_begin_ns'],v['work_end_ns'],v['wall_applied_ns'],v['physics_acquisition_begin_ns'],v['physics_acquisition_end_ns'],a['oldest_actuator_ns'] if int(a['oldest_actuator_ns']) else v['wall_applied_ns'],v['coil_source_ns'],v['coil_bits'],a['torque_nm'],sum(w['solver_omega_rad_s'] for w in p['wheels'][2:])/2,1.5624998923158273e-05,s['sleeping']]
   vals += [w['solver_omega_rad_s'] for w in v['physics']['wheels']]
   vals += s['rear_mean_rad_s'] or [0]*320
   print(*vals,file=f);prev=end
source=(root/'vecu/drive/drive_controller.cpp').read_text().replace('#include <algorithm>','#include <algorithm>\n#include <iostream>')
source=source.replace('    monitor(now_ns);\n    return result;','''    if(now_ns>272852964856476ULL && (result.wheel_speed!=SensorDecision::Accepted || result.hv!=SensorDecision::Accepted)) {
        std::cerr<<"sensor_reject at="<<now_ns<<" wheel="<<int(result.wheel_speed)<<" hv="<<int(result.hv);
        if(sensors.wheel_speed)std::cerr<<" wheel_source="<<sensors.wheel_speed->identity.source_time_ns<<" wheel_input="<<sensors.wheel_speed->input_time_ns<<" wheel_value="<<sensors.wheel_speed->value;
        if(sensors.hv)std::cerr<<" hv_source="<<sensors.hv->identity.source_time_ns<<" hv_input="<<sensors.hv->input_time_ns;
        std::cerr<<std::endl;
    }
    monitor(now_ns);
    return result;''')
source=source.replace('    decision_.active = false; decision_.selected_target_nm = 0;', '''    if(fault==DriveGateFault::LocalInputsUnavailable) {
      std::cerr<<"local_failure at="<<now_ns;
      if(speed_)std::cerr<<" speed_source="<<speed_->identity.source_time_ns<<" speed_input="<<speed_->input_time_ns;
      if(hv_)std::cerr<<" hv_source="<<hv_->identity.source_time_ns<<" hv_input="<<hv_->input_time_ns;
      std::cerr<<std::endl;
    }
    decision_.active = false; decision_.selected_target_nm = 0;''',1)
(work/'drive_diagnostic.cpp').write_text(source)
b=root/'build/m7-functional/tests/integration/carla/m7_1g';flags=(b/'CMakeFiles/m7_carla_wall_owner.dir/flags.make').read_text();inc=next(l.split(' = ',1)[1] for l in flags.splitlines() if l.startswith('CXX_INCLUDES'))
link=shlex.split((b/'CMakeFiles/m7_carla_wall_owner.dir/link.txt').read_text());libs=link[4:]
cmd=['c++','-std=c++17','-O0',*shlex.split(inc),str(work/'replay11.cpp'),str(work/'drive_diagnostic.cpp'),'-o',str(work/'replay11'),*libs]
(work/'replay11-build-args.json').write_text(json.dumps(cmd,indent=2)+'\n');subprocess.run(cmd,cwd=b,check=True)
with (work/'replay11-input.txt').open() as inp,(work/'replay11-output.log').open('w') as out: subprocess.run([str(work/'replay11')],stdin=inp,stdout=out,stderr=subprocess.STDOUT,check=True)
print((work/'replay11-output.log').read_text())

#!/usr/bin/env python3
"""Isolated logging-only SDK comparison. Never replaces the default SDK/install."""
import difflib
import fcntl
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import run


def main():
    root=run.ROOT
    source=root/'build/m5-someip-deps/vsomeip'
    normal=root/'build/m5-someip-normal'
    out=root/'build/m5-someip-shutdown-observe';out.mkdir(exist_ok=False)
    clone=out/'source';shutil.copytree(source,clone,ignore=shutil.ignore_patterns('.git'))
    relative=Path('implementation/endpoints/src/tcp_server_endpoint_impl.cpp')
    p=clone/relative;before=p.read_text()
    anchor='        if (its_data.is_sending_ && _error) {'
    assert before.count(anchor)==1
    after=before.replace(anchor,'''        VSOMEIP_WARNING_P << "SD_SHUTDOWN_OBSERVE remote=" << remote_
                          << " sending=" << its_data.is_sending_ << " error=" << _error.value()
                          << " queue_bytes=" << its_data.queue_size_
                          << " train_bytes=" << (its_data.train_ && its_data.train_->buffer_ ? its_data.train_->buffer_->size() : 0)
                          << " dispatched_trains=" << its_data.dispatched_trains_.size()
                          << " reschedule=" << (its_data.is_sending_ && static_cast<bool>(_error));
'''+anchor)
    p.write_text(after)
    (out/'observe.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+str(relative),tofile='b/'+str(relative))))
    sdk=normal/'sdk'
    entry=next(r for r in json.loads((sdk/'compile_commands.json').read_text()) if r['file'].endswith(str(relative)))
    compile_cmd=shlex.split(entry['command']);old_object=compile_cmd[compile_cmd.index('-o')+1]
    compile_cmd[compile_cmd.index('-o')+1]=str(out/'tcp_server_endpoint_impl.cpp.o')
    compile_cmd[compile_cmd.index('-c')+1]=str(p)
    lines=subprocess.check_output(['ninja','-C',str(sdk),'-t','commands','libvsomeip3.so.3.7.6'],text=True).splitlines()
    link=shlex.split(lines[-1].split('&&')[1].strip())
    lib=out/'lib';lib.mkdir()
    link[link.index(old_object)]=str(out/'tcp_server_endpoint_impl.cpp.o')
    link[link.index('-o')+1]=str(lib/'libvsomeip3.so.3.7.6')
    run.save(out/'commands.json',{'compile':compile_cmd,'link':link,'cwd':str(sdk),'base_commit':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()})
    for label,cmd in [('compile',compile_cmd),('link',link)]:
        with (out/(label+'.txt')).open('w') as log:subprocess.run(cmd,cwd=sdk,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    for f in (normal/'install/lib').iterdir():
        if not f.name.startswith('libvsomeip3.so'):(lib/f.name).symlink_to(f.resolve())
    (lib/'libvsomeip3.so.3').symlink_to('libvsomeip3.so.3.7.6');(lib/'libvsomeip3.so').symlink_to('libvsomeip3.so.3')
    objects=[Path(a) if Path(a).is_absolute() else sdk/a for a in link if a.endswith('.o')]
    run.save(out/'identity.json',{'patched_library':hashlib.sha256((lib/'libvsomeip3.so.3.7.6').read_bytes()).hexdigest(),'patch_sha256':hashlib.sha256((out/'observe.patch').read_bytes()).hexdigest(),'objects':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in objects}})

if __name__=='__main__':
    with run.open_lock() as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);main()

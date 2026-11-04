#!/usr/bin/env python3
"""Build an isolated observation SDK; do not mutate the pinned dependency/build."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
from build import PIN
from run import ROOT, open_lock


def instrument(source):
    def change(relative, edits):
        path=source/relative
        original=path.read_text();text=original
        for old,new,count in edits:
            if text.count(old)!=count:raise ValueError('unexpected pinned source: '+relative+' '+old[:70])
            text=text.replace(old,new)
        path.write_text('#include "sdk_observation.hpp"\n'+text)
    ns='stratadrive::sdk_observation::'
    change('implementation/runtime/src/application_impl.cpp',[
        ('bool application_impl::init() {','bool application_impl::init() {\n    '+ns+'init();',1),
        ('    stopping_ = false;\n\n    VSOMEIP_INFO << "Stopped thread',
         '    '+ns+'flush();\n    stopping_ = false;\n\n    VSOMEIP_INFO << "Stopped thread',1),
        ('void application_impl::on_message(std::shared_ptr<message>&& _message) {',
         'void application_impl::on_message(std::shared_ptr<message>&& _message) {\n    const auto observed_key = '+ns+'key(_message);\n    '+ns+'record("app-message", observed_key);',1),
        ('std::make_shared<sync_handler>([handler, _message]() { handler(_message); })',
         'std::make_shared<sync_handler>([handler, _message, observed_key]() {\n                    '+ns+'record("handler-enter", observed_key);\n                    handler(_message);\n                    '+ns+'record("handler-exit", observed_key);\n                })',1),
        ('                its_sync_handler->session_id_ = _message->get_session();\n                handlers_.push_back(its_sync_handler);',
         '                its_sync_handler->session_id_ = _message->get_session();\n                handlers_.push_back(its_sync_handler);\n                '+ns+'record("handler-queued", observed_key);',1)])
    for role in ('client','server'):
        relative=f'implementation/endpoints/src/tcp_{role}_endpoint_impl.cpp'
        text=(source/relative).read_text()
        if role=='server':
            signature='void tcp_server_endpoint_impl::connection::receive_cbk(boost::system::error_code const& _error, size_t _bytes) {'
            pointer='&recv_buffer_[its_iteration_gap]'
            send='    message_buffer_ptr_t its_buffer = _it->second.queue_.front().first;'
            send_point='    _it->second.is_sending_ = true;'
            send_trace=ns+'wire("tcp-send", its_buffer->data(), its_buffer->size());'
        else:
            start=text.index('void tcp_client_endpoint_impl::receive_cbk(')
            signature=text[start:text.index('{',start)+1]
            pointer='&(*_recv_buffer)[its_iteration_gap]'
            send_point='        if (socket_->is_open()) {\n            socket_->async_write('
            send_trace=ns+'wire("tcp-send", _entry.first->data(), _entry.first->size());'
        old=f'its_host->on_message({pointer}, current_message_size,'
        edits=[(signature,signature+'\n    const auto observed_receive = '+ns+'stamp();',1),
               (old,ns+'wire("tcp-receive", '+pointer+', current_message_size, observed_receive);\n                            '+ns+'wire("tcp-message", '+pointer+', current_message_size);\n                            '+old,2)]
        if role=='server':edits.append((send_point,'    '+send_trace+'\n'+send_point,1))
        else:edits.append((send_point,'        if (socket_->is_open()) {\n            '+send_trace+'\n            socket_->async_write(',1))
        change(relative,edits)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('profile',choices=('normal','asan','tsan'));p.add_argument('output',type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=out/'source';original=ROOT/'build/m5-someip-deps/vsomeip';commands=[]
    def run(cmd):
        row={'command':list(map(str,cmd))};commands.append(row)
        with (out/f'command-{len(commands):02}.txt').open('w') as log:
            row['exit']=subprocess.run(row['command'],stdout=log,stderr=subprocess.STDOUT).returncode
        (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        print(row,flush=True)
        if row['exit']:raise RuntimeError('observation SDK build failed')
    with open_lock() as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert subprocess.check_output(['git','-C',str(original),'rev-parse','HEAD'],text=True).strip()==PIN
        assert not subprocess.check_output(['git','-C',str(original),'status','--porcelain'])
        run(['git','clone','--no-hardlinks',original,source]);instrument(source)
        patch=subprocess.check_output(['git','-C',str(source),'diff']);(out/'sdk.patch').write_bytes(patch)
        helper=Path(__file__).with_name('sdk_observation.hpp');(out/helper.name).write_bytes(helper.read_bytes())
        flags='-O1 -g -fno-omit-frame-pointer -I'+str(helper.parent)
        sanitizer={'normal':'','asan':'address,undefined','tsan':'thread'}[a.profile]
        if sanitizer:flags+=' -fsanitize='+sanitizer
        install=ROOT/f'build/m5-someip-{a.profile}/install'
        run(['cmake','-S',source,'-B',out/'sdk','-G','Ninja','-DCMAKE_BUILD_TYPE=RelWithDebInfo',
             '-DCMAKE_CXX_FLAGS='+flags,'-DCMAKE_INSTALL_PREFIX='+str(out/'install'),'-DCMAKE_PREFIX_PATH='+str(install),
             '-DBoost_NO_SYSTEM_PATHS=ON','-DENABLE_SIGNAL_HANDLING=OFF','-DENABLE_MULTIPLE_ROUTING_MANAGERS=OFF',
             '-DDISABLE_DLT=ON','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'])
        run(['cmake','--build',out/'sdk','--parallel','2']);run(['cmake','--install',out/'sdk'])
        (out/'manifest.json').write_text(json.dumps({'pin':PIN,'profile':a.profile,'patch_sha256':hashlib.sha256(patch).hexdigest(),
            'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),
            'libraries':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in (out/'install/lib').glob('*.so*') if f.is_file()},
            'library_path':str(out/'install/lib')+':'+str(install/'lib')},indent=2)+'\n')


if __name__=='__main__':main()

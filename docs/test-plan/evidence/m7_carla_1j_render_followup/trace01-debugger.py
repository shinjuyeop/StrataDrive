import gdb,json,time
from pathlib import Path
OUT=Path('/d/shin/stratadrive-tools/m7-source/render-followup-20261026-trace01')
started=time.monotonic()
seq=0
record={'started_monotonic':started,'inferior_pid':None,'stops':[]}
def val(expr):
    try:return str(gdb.parse_and_eval(expr))
    except Exception as error:return 'ERROR: '+str(error)
def integer(expr):
    return int(gdb.parse_and_eval(expr))
def emit(kind,fields):
    global seq
    seq+=1
    fields.update(seq=seq,kind=kind,wall_s=time.monotonic()-started,thread=gdb.selected_thread().global_num if gdb.selected_thread() else None)
    with (OUT/'events.jsonl').open('a') as stream:stream.write(json.dumps(fields)+'\n')
class Trace(gdb.Breakpoint):
    def __init__(self,spec,kind,expressions):
        self.kind,self.expressions=kind,expressions
        super().__init__(spec,internal=True)
    def stop(self):
        emit(self.kind,{label:val(expr) for label,expr in self.expressions.items()})
        return False
class Queues(gdb.Breakpoint):
    def __init__(self):
        self.last=-100
        super().__init__('FDistanceFieldAsyncQueue::ProcessAsyncTasks()',internal=True)
    def stop(self):
        now=time.monotonic()-started
        if now-self.last<10:return False
        self.last=now
        fields={}
        exprs={'distance_tasks':'GDistanceFieldAsyncQueue->ReferencedTasks.ArrayNum',
          'shader_outstanding':'GShaderCompilingManager->NumOutstandingJobs',
          'shader_external':'GShaderCompilingManager->NumExternalJobs',
          'shader_queue':'GShaderCompilingManager->CompileQueue.ArrayNum',
          'shader_finalize_allocated':'GShaderCompilingManager->PendingFinalizeShaderMaps.Pairs.Elements.Data.ArrayNum',
          'shader_finalize_free':'GShaderCompilingManager->PendingFinalizeShaderMaps.Pairs.Elements.NumFreeIndices',
          'shader_maps_allocated':'GShaderCompilingManager->ShaderMapJobs.Pairs.Elements.Data.ArrayNum',
          'shader_maps_free':'GShaderCompilingManager->ShaderMapJobs.Pairs.Elements.NumFreeIndices'}
        for label,expr in exprs.items():
            try:fields[label]=integer(expr)
            except Exception as error:fields[label]='ERROR: '+str(error)
        emit('queues',fields)
        record['inferior_pid']=gdb.selected_inferior().pid
        (OUT/'latest-queues.json').write_text(json.dumps(fields,indent=2)+'\n')
        (OUT/'gdb-event.json').write_text(json.dumps(record,indent=2)+'\n')
        return False
Trace('FDistanceFieldVolumeTexture::Initialize(UStaticMesh*)','volume_init',{'texture':'(void*)this','volume':'(void*)&this->VolumeData','mesh':'(void*)InStaticMesh','mesh_name_id':'InStaticMesh->NamePrivate'})
Trace('FDistanceFieldVolumeTexture::~FDistanceFieldVolumeTexture()','volume_destroy',{'texture':'(void*)this','volume':'(void*)&this->VolumeData','mesh':'(void*)this->StaticMesh'})
Trace('/d/shin/stratadrive-tools/UnrealEngine_4.26/Engine/Source/Runtime/Engine/Private/StaticMeshRender.cpp:217','proxy_cache',{'proxy':'(void*)this','data':'(void*)this->DistanceFieldData','mesh':'(void*)this->StaticMesh','mesh_name_id':'this->StaticMesh->NamePrivate','render_data':'(void*)this->RenderData'})
Trace('FStaticMeshSceneProxy::~FStaticMeshSceneProxy()','proxy_destroy',{'proxy':'(void*)this','data':'(void*)this->DistanceFieldData','mesh':'(void*)this->StaticMesh'})
Queues()
def stopped(event):
    if isinstance(event,gdb.SignalEvent):record['stops'].append(event.stop_signal)
    record['inferior_pid']=gdb.selected_inferior().pid
    (OUT/'gdb-event.json').write_text(json.dumps(record,indent=2)+'\n')
def exited(event):
    record['inferior_exit_code']=getattr(event,'exit_code',None)
    (OUT/'gdb-event.json').write_text(json.dumps(record,indent=2)+'\n')
gdb.events.stop.connect(stopped)
gdb.events.exited.connect(exited)
gdb.execute('run')
if gdb.selected_thread():
    record['postmortem']={key:val(key) for key in ('(void*)this','(void*)&this->VolumeData')}
    gdb.execute('bt 20')
    gdb.execute('info registers rax rdi rip')
    try:
        gdb.execute('frame 1')
        record['postmortem'].update({key:val(key) for key in (
          '(void*)Proxy','(void*)((FStaticMeshSceneProxy*)Proxy)->DistanceFieldData',
          '(void*)((FStaticMeshSceneProxy*)Proxy)->StaticMesh',
          '((FStaticMeshSceneProxy*)Proxy)->StaticMesh->NamePrivate',
          '(void*)((FStaticMeshSceneProxy*)Proxy)->RenderData',
          '((FStaticMeshSceneProxy*)Proxy)->RenderData->LODResources.Array',
          '(void*)((FStaticMeshLODResources**)((FStaticMeshSceneProxy*)Proxy)->RenderData->LODResources.Array.AllocatorInstance.Data)[0]->DistanceFieldData')})
    except Exception as error:record['postmortem_error']=str(error)
    (OUT/'gdb-event.json').write_text(json.dumps(record,indent=2)+'\n')
    gdb.execute('thread apply all bt 3')
gdb.execute('quit')

import ctypes as c,uuid,sys
class Guid(c.Structure):_fields_=[('raw',c.c_byte*16)]
def guid(s):return Guid.from_buffer_copy(uuid.UUID(s).bytes_le)
dll=c.CDLL(sys.argv[1]);f=dll.DxcCreateInstance;f.argtypes=[c.POINTER(Guid),c.POINTER(Guid),c.POINTER(c.c_void_p)];f.restype=c.c_int
ptr=c.c_void_p;uint=c.c_uint;outptr=c.POINTER(ptr)
def create(clsid,iid):
 out=ptr();assert f(c.byref(guid(clsid)),c.byref(guid(iid)),c.byref(out))==0;return out
def method(obj,i,result,*params):
 v=c.cast(obj,c.POINTER(c.POINTER(ptr))).contents;return c.CFUNCTYPE(result,ptr,*params)(v[i])
def release(obj):return method(obj,2,uint)(obj)
compiler=create('73e22d93-e6ce-47f3-b5bf-f0664f39c1b0','8c210bf3-011f-4422-8d70-6f9acb8db617')
library=create('6245d6af-66e0-48fd-80b4-4d271796748c','e5204dc7-d18c-4c3c-bdfb-851673980fe7')
text=b'float4 main() : SV_Target { return float4(1,0,0,1); }';blob=ptr()
assert method(library,8,c.c_int,ptr,uint,uint,outptr)(library,text,len(text),65001,c.byref(blob))==0
result=ptr();args=(c.c_wchar_p*1)('-spirv')
hr=method(compiler,5,c.c_int,ptr,c.c_wchar_p,c.c_wchar_p,c.c_wchar_p,c.POINTER(c.c_wchar_p),uint,ptr,uint,ptr,outptr)(compiler,blob,'probe.hlsl','main','ps_6_0',args,1,None,0,None,c.byref(result))
print('compiled',hr,flush=True)
if result.value:
 status=c.c_int();method(result,5,c.c_int,c.POINTER(c.c_int))(result,c.byref(status));print('status',status.value,flush=True);release(result)
release(blob);release(library);release(compiler);print('released',flush=True)

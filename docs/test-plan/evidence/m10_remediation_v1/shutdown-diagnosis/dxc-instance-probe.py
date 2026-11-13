import ctypes as c,uuid,sys
class Guid(c.Structure):_fields_=[('raw',c.c_byte*16)]
def guid(s):return Guid.from_buffer_copy(uuid.UUID(s).bytes_le)
dll=c.CDLL(sys.argv[1]);out=c.c_void_p()
f=dll.DxcCreateInstance;f.argtypes=[c.POINTER(Guid),c.POINTER(Guid),c.POINTER(c.c_void_p)];f.restype=c.c_int
hr=f(c.byref(guid('73e22d93-e6ce-47f3-b5bf-f0664f39c1b0')),c.byref(guid('8c210bf3-011f-4422-8d70-6f9acb8db617')),c.byref(out))
print('created',hr,flush=True)
if out.value:
    v=c.cast(out,c.POINTER(c.POINTER(c.c_void_p))).contents
    release=c.CFUNCTYPE(c.c_uint,c.c_void_p)(v[2]);print('released',release(out),flush=True)

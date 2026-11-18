import ctypes
from pathlib import Path
import threading
import numpy as np


class CudaResize:
    def __init__(self,library):
        self.owner=threading.get_ident();self.handle=ctypes.c_void_p()
        self.library=ctypes.CDLL(str(Path(library).resolve()))
        self.create=self.library.strata_cuda_resize_create
        self.create.argtypes=[ctypes.POINTER(ctypes.c_void_p)];self.create.restype=ctypes.c_int
        self.call=self.library.strata_cuda_resize
        self.call.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t]
        self.call.restype=ctypes.c_int
        self.destroy=self.library.strata_cuda_resize_destroy
        self.destroy.argtypes=[ctypes.c_void_p];self.destroy.restype=None
        self.output=np.empty((960,960,3),np.uint8)
        code=self.create(ctypes.byref(self.handle))
        if code:raise RuntimeError('CUDA resize creation: '+str(code))
        self.threads=0

    def resize(self,raw):
        if threading.get_ident()!=self.owner:raise ValueError('single synchronous GPU resize owner')
        if not self.handle.value or type(raw) is not bytes or len(raw)!=2560*1536*4:
            raise ValueError('exact original BGRA and open workspace')
        code=self.call(self.handle,ctypes.c_char_p(raw),len(raw),self.output.ctypes.data,self.output.nbytes)
        if code:raise RuntimeError('CUDA resize failed: '+str(code))
        return self.output

    def close(self):
        if self.handle.value:
            self.destroy(self.handle);self.handle=ctypes.c_void_p()

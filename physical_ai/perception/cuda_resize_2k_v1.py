"""Optional CUDA implementation of the original exact 2K bilinear resize."""
import ctypes
import os
from pathlib import Path
import threading

import numpy as np

from .contract import sha256_file
from .tensor_2k_v1 import TensorKernelBackend


class CudaResize:
    """One inference owner, persistent buffers, blocking completion, no fallback.

    The returned CPU RGB array is borrowed until the next call. Tensor conversion,
    image-health checks and inference retain their existing implementations.
    """
    kind = 'cuda-two-pass-exact-v1'

    @property
    def threads(self):
        return 0

    @threads.setter
    def threads(self, value):
        if value != 0:
            raise ValueError('CUDA resize has no CPU resize workers')

    def __init__(self, library, digest):
        path = Path(library).resolve()
        if sha256_file(path) != digest:
            raise ValueError('pinned CUDA resize library required')
        # Capture constructs the backend before handing it to its worker. Bind
        # ownership on first use, just like the existing tensor workspace.
        self.owner = None
        self.lock = threading.Lock()
        self.handle = ctypes.c_void_p()
        self.failed = False
        self.metadata = dict(kind=self.kind, library=str(path), sha256=digest,
            cpu_resize_threads=0, host_wait='cudaEventBlockingSync', calls=0,
            failures=0, closed=False, owner_thread_id=None, owner_native_tid=None)
        self.library = ctypes.CDLL(str(path))
        self.create = self.library.strata_cuda_resize_create
        self.create.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.create.restype = ctypes.c_int
        self.call = self.library.strata_cuda_resize
        self.call.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                              ctypes.c_void_p, ctypes.c_size_t]
        self.call.restype = ctypes.c_int
        self.destroy = self.library.strata_cuda_resize_destroy
        self.destroy.argtypes = [ctypes.c_void_p]
        self.destroy.restype = None
        self.output = np.empty((960, 960, 3), np.uint8)
        code = self.create(ctypes.byref(self.handle))
        if code:
            raise RuntimeError(f'CUDA resize creation failed: {code}')

    def resize(self, raw):
        if type(raw) is not bytes or len(raw) != 2560 * 1536 * 4:
            raise ValueError('exact immutable native BGRA required')
        with self.lock:
            owner = threading.get_ident()
            if self.owner is None:
                self.owner = owner
                self.metadata.update(owner_thread_id=owner, owner_native_tid=threading.get_native_id())
            if owner != self.owner:
                raise ValueError('single synchronous CUDA resize owner')
            if not self.handle.value or self.failed:
                raise RuntimeError('closed or failed CUDA resize workspace')
            code = self.call(self.handle, ctypes.c_char_p(raw), len(raw),
                             self.output.ctypes.data, self.output.nbytes)
            if code:
                self.failed = True
                self.metadata['failures'] += 1
                raise RuntimeError(f'CUDA resize failed: {code}')
            self.metadata['calls'] += 1
            return self.output

    def close(self):
        # A close from another thread waits until the synchronous call completes;
        # it cannot free pinned/device memory while a transfer still owns it.
        with self.lock:
            if self.handle.value:
                handle, self.handle = self.handle, ctypes.c_void_p()
                self.destroy(handle)
            self.metadata['closed'] = True

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass  # A failed constructor may not yet have created its lock/handle.


class CudaTensorKernelBackend(TensorKernelBackend):
    def __init__(self, *args, **kwargs):
        path = os.environ.get('STRATADRIVE_M10_CUDA_RESIZE_LIBRARY')
        digest = os.environ.get('STRATADRIVE_M10_CUDA_RESIZE_SHA256')
        if not path or not digest:
            raise ValueError('explicit frozen CUDA resize library and digest')
        # Existing detector initialization establishes the CUDA blocking-wait
        # policy before the optional resize allocates its stream and buffers.
        super().__init__(*args, **kwargs)
        self.resize = CudaResize(path, digest)

    def close(self):
        self.resize.close()

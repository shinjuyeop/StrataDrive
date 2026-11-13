"""Explicit per-process CUDA host wait policy; no host clock or arithmetic change."""
import ctypes
from pathlib import Path


def blocking_sync():
    # Called after ORT's pinned dependency preload, before constructing a session.
    paths={line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
           if '/libcudart.so.' in line}
    if len(paths)!=1:raise ValueError('one loaded CUDA runtime required')
    path=paths.pop();lib=ctypes.CDLL(path)
    lib.cudaGetDeviceFlags.argtypes=[ctypes.POINTER(ctypes.c_uint)]
    lib.cudaSetDeviceFlags.argtypes=[ctypes.c_uint]
    before=ctypes.c_uint();after=ctypes.c_uint()
    if lib.cudaGetDeviceFlags(ctypes.byref(before))!=0:raise RuntimeError('CUDA device flags unavailable')
    # Replace only scheduling bits (mask7). Preserve all other context flags.
    requested=(before.value & ~7)|4
    if lib.cudaSetDeviceFlags(requested)!=0:raise RuntimeError('CUDA blocking host wait rejected')
    if lib.cudaGetDeviceFlags(ctypes.byref(after))!=0 or after.value!=requested:
        raise RuntimeError('CUDA blocking host wait did not take effect')
    return dict(runtime=path,before=before.value,after=after.value,scope='current process CUDA device')

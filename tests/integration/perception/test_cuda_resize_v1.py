import ctypes
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from physical_ai.perception.cuda_resize_2k_v1 import CudaResize, CudaTensorKernelBackend
from endurance_host_v1 import pipeline_backend


class CudaResizeBoundaryTests(unittest.TestCase):
    def factory(self, folder):
        path=Path(folder)/'fixture.so';path.write_bytes(b'fixture; never loaded')
        def create(pointer):
            ctypes.cast(pointer,ctypes.POINTER(ctypes.c_void_p))[0]=ctypes.c_void_p(42)
            return 0
        library=Mock()
        library.strata_cuda_resize_create=Mock(side_effect=create)
        library.strata_cuda_resize=Mock(return_value=0)
        library.strata_cuda_resize_destroy=Mock()
        with patch('physical_ai.perception.cuda_resize_2k_v1.ctypes.CDLL',return_value=library):
            resize=CudaResize(path,hashlib.sha256(path.read_bytes()).hexdigest())
        return resize,library,path

    def test_changed_binary_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'unknown.so';path.write_bytes(b'unknown')
            with patch('physical_ai.perception.cuda_resize_2k_v1.ctypes.CDLL') as load:
                with self.assertRaises(ValueError):CudaResize(path,'0'*64)
                load.assert_not_called()

    def test_constructor_handoff_binds_first_worker_and_rejects_other_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            resize,lib,_=self.factory(folder);errors=[];raw=bytes(2560*1536*4)
            def work():
                try:resize.resize(raw)
                except Exception as error:errors.append(error)
            thread=threading.Thread(target=work);thread.start();thread.join(5)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
            self.assertEqual(resize.metadata['calls'],1)
            with self.assertRaisesRegex(ValueError,'owner'):resize.resize(raw)
            self.assertEqual(lib.strata_cuda_resize.call_count,1)
            resize.close();resize.close();lib.strata_cuda_resize_destroy.assert_called_once()

    def test_runtime_failure_latches_without_returning_stale_output(self):
        with tempfile.TemporaryDirectory() as folder:
            resize,lib,_=self.factory(folder);lib.strata_cuda_resize.return_value=700
            for _ in range(2):
                with self.assertRaises(RuntimeError):resize.resize(bytes(2560*1536*4))
            self.assertEqual(lib.strata_cuda_resize.call_count,1)
            self.assertEqual((resize.metadata['calls'],resize.metadata['failures']),(0,1))
            resize.close()

    def test_invalid_input_and_cpu_workers_cannot_invoke_device(self):
        with tempfile.TemporaryDirectory() as folder:
            resize,lib,_=self.factory(folder)
            for raw in (b'',bytearray(2560*1536*4),bytes(2560*1536*4-1)):
                with self.assertRaises(ValueError):resize.resize(raw)
            with self.assertRaises(ValueError):resize.threads=4
            self.assertEqual(resize.threads,0);lib.strata_cuda_resize.assert_not_called();resize.close()
            with self.assertRaises(RuntimeError):resize.resize(bytes(2560*1536*4))

    def test_close_waits_for_inflight_transfer(self):
        with tempfile.TemporaryDirectory() as folder:
            resize,lib,_=self.factory(folder);entered=threading.Event();release=threading.Event();closed=threading.Event()
            def call(*_):entered.set();self.assertTrue(release.wait(3));return 0
            lib.strata_cuda_resize.side_effect=call
            worker=threading.Thread(target=lambda:resize.resize(bytes(2560*1536*4)))
            closer=threading.Thread(target=lambda:(resize.close(),closed.set()))
            worker.start();self.assertTrue(entered.wait(3));closer.start()
            self.assertFalse(closed.wait(.02));lib.strata_cuda_resize_destroy.assert_not_called()
            release.set();worker.join(3);closer.join(3);self.assertTrue(closed.is_set())
            lib.strata_cuda_resize_destroy.assert_called_once()

    def test_explicit_factory_requires_digest_workspace_and_zero_cpu_workers(self):
        expected=dict(STRATADRIVE_M10_TENSOR_WORKSPACE='1',STRATADRIVE_M10_CUDA_RESIZE_LIBRARY='/fixture',
                      STRATADRIVE_M10_CUDA_RESIZE_SHA256='a'*64)
        with patch.dict(os.environ,expected,clear=True):self.assertIs(pipeline_backend(object()),CudaTensorKernelBackend)
        for key in expected:
            env=expected.copy();env.pop(key)
            with patch.dict(os.environ,env,clear=True),self.assertRaises(ValueError):pipeline_backend(object())
        with patch.dict(os.environ,dict(expected,STRATADRIVE_M10_RESIZE_THREADS='4'),clear=True),self.assertRaises(ValueError):pipeline_backend(object())


if __name__=='__main__':unittest.main()

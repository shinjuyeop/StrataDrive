"""Submit the fixed six crops to a separate batch-six TensorRT engine."""

from ctypes import CDLL, c_bool, c_int, c_ubyte, c_void_p

import numpy as np
import tensorrt as trt

from quality_cached_views import CachedFrameViews
from quality_latency_cuda import GpuBuffers, checked, cu


class BatchEngine(GpuBuffers):
    def __init__(self, engine_path, library, outputs):
        super().__init__()
        self.logger = trt.Logger(trt.Logger.ERROR)
        self.runtime = trt.Runtime(self.logger)
        self.engine = self.runtime.deserialize_cuda_engine(engine_path.read_bytes())
        if self.engine is None:
            raise ValueError("incompatible batch engine")
        self.ctx = self.engine.create_execution_context()
        self.buffers = {}
        self.host = {}
        try:
            self.stream = checked(cu.cudaStreamCreate())
            self.callback(lambda: checked(cu.cudaStreamDestroy(self.stream)))
            for key in ["images", *outputs]:
                shape = tuple(self.engine.get_tensor_shape(key))
                dtype = np.dtype(trt.nptype(self.engine.get_tensor_dtype(key)))
                if not shape or shape[0] != 6 or min(shape) <= 0:
                    raise ValueError(f"unexpected batch tensor {key}")
                size = int(np.prod(shape)) * dtype.itemsize
                ptr = self.allocate(size)
                self.buffers[key] = ptr
                if not self.ctx.set_tensor_address(key, ptr):
                    raise ValueError(f"failed to bind {key}")
                if key == "images":
                    if shape != (6, 3, 960, 960) or dtype != np.float32:
                        raise ValueError("unexpected batch input")
                    self.stride = size // 6
                else:
                    pinned = checked(cu.cudaMallocHost(size))
                    self.callback(lambda p=pinned: checked(cu.cudaFreeHost(p)))
                    view = np.ctypeslib.as_array((c_ubyte * size).from_address(pinned))
                    self.host[key] = view.view(dtype).reshape(shape)
            self.crop = CDLL(str(library.resolve())).enqueue_quality_crop
            self.crop.argtypes = [
                c_void_p,
                c_int,
                c_int,
                c_int,
                c_bool,
                c_void_p,
                c_void_p,
                c_void_p,
                c_void_p,
            ]
            self.crop.restype = c_int
        except BaseException:
            self.close()
            raise

    def infer(self, crops, windows):
        if len(windows) != 6:
            raise ValueError("six fixed windows required")
        for i, (_, rect, flip) in enumerate(windows):
            x, y, r, b = rect
            ptr = self.buffers["images"] + i * self.stride
            if self.crop(
                crops.pixels,
                x,
                y,
                r - x,
                flip,
                crops.axis(r - x, 960),
                crops.axis(b - y, 960),
                ptr,
                int(self.stream),
            ):
                raise RuntimeError("batch crop enqueue")
        if not self.ctx.execute_async_v3(self.stream):
            raise RuntimeError("batch inference enqueue")
        for key, arr in self.host.items():
            checked(
                cu.cudaMemcpyAsync(
                    arr.ctypes.data,
                    self.buffers[key],
                    arr.nbytes,
                    cu.cudaMemcpyKind.cudaMemcpyDeviceToHost,
                    self.stream,
                )
            )
        checked(cu.cudaStreamSynchronize(self.stream))
        return {
            (rect, flip): {
                key: arr[i]
                if key in ("car_boxes", "car_logits", "adjacent_delta")
                else arr[i : i + 1]
                for key, arr in self.host.items()
            }
            for i, (_, rect, flip) in enumerate(windows)
        }


class BatchViews(CachedFrameViews):
    def __init__(self, detector, indices, batch):
        super().__init__(detector, indices)
        self.batch = batch

    def prepare(self, image):
        self.batch_ready = False
        return super().prepare(image)

    def forward(self, rect, flip=False):
        if not self.batch_ready:
            self.outputs.update(self.batch.infer(self.crops, self.windows))
            self.count += len(self.windows)
            self.batch_ready = True
        return super().forward(rect, flip)

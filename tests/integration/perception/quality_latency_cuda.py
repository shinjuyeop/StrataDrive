"""Reusable native RGB crop buffers and blocking CUDA or TensorRT inference for offline replay."""

from contextlib import ExitStack
from ctypes import CDLL, c_bool, c_int, c_void_p, c_ubyte

from cuda.bindings import runtime as cu
import numpy as np


def checked(result):
    error, *values = result
    if error != cu.cudaError_t.cudaSuccess:
        raise RuntimeError(str(error))
    return values[0] if values else None


def coefficients(size, output=960):
    """Pillow clipped, normalized bilinear taps, rounded to 22 fractional bits."""
    scale = size / output
    radius = max(scale, 1.0)
    center = (np.arange(output, dtype=float) + 0.5) * scale
    start = np.maximum(0, (center - radius + 0.5).astype(int))
    indices = start[:, None] + np.arange(9)
    distance = np.abs(indices - center[:, None] + 0.5) / radius
    weights = np.where(indices < size, np.maximum(0.0, 1.0 - distance), 0.0)
    taps = (weights / weights.sum(axis=1)[:, None] * (1 << 22) + 0.5).astype(np.int32)
    first = (taps[:, 0] == 0).astype(int)
    out = np.empty((output, 9), np.int32)
    out[:, 0] = start + first
    out[:, 1:] = np.take_along_axis(taps, first[:, None] + np.arange(8), axis=1)
    if np.any((first == 0) & (taps[:, 8] != 0)):
        raise ValueError("crop filter exceeds available taps")
    return out


class GpuBuffers(ExitStack):
    def allocate(self, nbytes):
        ptr = checked(cu.cudaMalloc(nbytes))
        self.callback(lambda: checked(cu.cudaFree(ptr)))
        return ptr

    @staticmethod
    def upload(dst, values):
        checked(
            cu.cudaMemcpy(
                dst,
                values.ctypes.data,
                values.nbytes,
                cu.cudaMemcpyKind.cudaMemcpyHostToDevice,
            )
        )


class CropInput(GpuBuffers):
    def __init__(self, library):
        super().__init__()
        self.kernel = CDLL(str(library.resolve())).prepare_quality_crop
        self.kernel.argtypes = [
            c_void_p,
            c_int,
            c_int,
            c_int,
            c_int,
            c_bool,
            c_void_p,
            c_void_p,
            c_int,
            c_int,
            c_bool,
            c_void_p,
        ]
        self.kernel.restype = c_int
        try:
            self.pixels = self.allocate(2560 * 1536 * 3)
            self.tensor = self.allocate(960 * 960 * 3 * 4)
        except Exception:
            self.close()
            raise
        self.axes = {}

    def frame(self, image):
        rgb = np.asarray(image)
        if (
            getattr(image, "mode", "RGB") != "RGB"
            or rgb.shape != (1536, 2560, 3)
            or rgb.dtype != np.uint8
            or not rgb.flags.c_contiguous
        ):
            raise ValueError("expected 2560x1536 RGB")
        self.upload(self.pixels, rgb)
        return rgb

    def axis(self, n, output):
        key = (n, output)
        if key not in self.axes:
            weights = coefficients(n, output)
            ptr = self.allocate(weights.nbytes)
            self.upload(ptr, weights)
            self.axes[key] = ptr
        return self.axes[key]

    def crop(self, rect, flip=False, yolo=False):
        x, y, r, b = rect
        if not (0 <= x < r <= 2560 and 0 <= y < b <= 1536):
            raise ValueError("crop outside native RGB")
        nx, ny = (640, 384) if yolo else (960, 960)
        code = self.kernel(
            self.pixels,
            2560,
            x,
            y,
            r - x,
            flip,
            self.axis(r - x, nx),
            self.axis(b - y, ny),
            nx,
            ny,
            yolo,
            self.tensor,
        )
        if code:
            raise RuntimeError(f"CUDA crop returned {code}")
        checked(cu.cudaStreamSynchronize(0))
        return self.tensor


class Engine(GpuBuffers):
    """One synchronous stream and private buffers per TensorRT execution owner."""

    def __init__(self, path, use_graph=True):
        import tensorrt as trt

        super().__init__()
        self.logger = trt.Logger(trt.Logger.ERROR)
        self.runtime = trt.Runtime(self.logger)
        self.engine = self.runtime.deserialize_cuda_engine(path.read_bytes())
        if self.engine is None:
            raise ValueError("incompatible TensorRT engine")
        self.ctx = self.engine.create_execution_context()
        self.use_graph = use_graph
        self.warmed = set()
        self.graphs = {}
        self.buffers = {}
        self.host = {}
        try:
            self.stream = checked(cu.cudaStreamCreate())
            self.callback(lambda: checked(cu.cudaStreamDestroy(self.stream)))
            for k in range(self.engine.num_io_tensors):
                name = self.engine.get_tensor_name(k)
                shape = self.engine.get_tensor_shape(name)
                dtype = trt.nptype(self.engine.get_tensor_dtype(name))
                arr = np.empty(tuple(shape), dtype=dtype)
                ptr = self.allocate(arr.nbytes)
                self.buffers[name] = ptr
                if name != "images":
                    pinned = checked(cu.cudaMallocHost(arr.nbytes))
                    self.callback(lambda p=pinned: checked(cu.cudaFreeHost(p)))
                    arr = (
                        np.ctypeslib.as_array(
                            (c_ubyte * arr.nbytes).from_address(pinned)
                        )
                        .view(dtype)
                        .reshape(tuple(shape))
                    )
                self.host[name] = arr
                if not self.ctx.set_tensor_address(name, ptr):
                    raise RuntimeError(name)
            if (
                self.host["images"].shape != (1, 3, 960, 960)
                or self.host["images"].dtype != np.float32
            ):
                raise ValueError("unexpected engine input")
        except Exception:
            self.close()
            raise

    def device(self, names, ptr):
        if ptr not in self.graphs:
            if not self.ctx.set_tensor_address("images", ptr):
                raise RuntimeError("TensorRT input binding failed")
            if self.use_graph and ptr in self.warmed:
                checked(
                    cu.cudaStreamBeginCapture(
                        self.stream,
                        cu.cudaStreamCaptureMode.cudaStreamCaptureModeThreadLocal,
                    )
                )
                try:
                    if not self.ctx.execute_async_v3(self.stream):
                        raise RuntimeError("TensorRT capture failed")
                finally:
                    graph = checked(cu.cudaStreamEndCapture(self.stream))
                try:
                    executable = checked(cu.cudaGraphInstantiate(graph, 0))
                finally:
                    checked(cu.cudaGraphDestroy(graph))
                self.graphs[ptr] = executable
                self.callback(lambda: checked(cu.cudaGraphExecDestroy(executable)))
            else:
                if not self.ctx.execute_async_v3(self.stream):
                    raise RuntimeError("TensorRT enqueue failed")
                self.warmed.add(ptr)
        if ptr in self.graphs:
            checked(cu.cudaGraphLaunch(self.graphs[ptr], self.stream))
        for n in names:
            arr = self.host[n]
            checked(
                cu.cudaMemcpyAsync(
                    arr.ctypes.data,
                    self.buffers[n],
                    arr.nbytes,
                    cu.cudaMemcpyKind.cudaMemcpyDeviceToHost,
                    self.stream,
                )
            )
        checked(cu.cudaStreamSynchronize(self.stream))
        return [self.host[n].copy() for n in names]

    def run(self, names, inputs):
        tensor = inputs["images"]
        if (
            tensor.shape != self.host["images"].shape
            or tensor.dtype != np.float32
            or not tensor.flags.c_contiguous
        ):
            raise ValueError("unexpected host tensor")
        self.upload(self.buffers["images"], tensor)
        return self.device(names, self.buffers["images"])

// Pillow bilinear integer filtering as in cuda_resize_2k_v1.cu, with an RGB crop input.
// Each axis row holds a start offset and up to eight 22-bit coefficients.
#include <cuda_runtime.h>
#include <cstdint>

constexpr int stride = 9;

__global__ void prepare(const uint8_t* rgb, int width, int x0, int y0,
                        int crop_width, bool flip, const int* horizontal,
                        const int* vertical, int nx, int ny, bool yolo, float* tensor) {
    const int idx = blockIdx.x * blockDim.x + threadIdx.x;
    const int plane = nx * (yolo ? nx : ny);
    if (idx >= plane) return;
    if (idx >= nx * ny) {
        for (int c = 0; c < 3; ++c) tensor[c * plane + idx] = 114.f;
        return;
    }
    const int x = idx % nx;
    const int y = idx / nx;
    const int* ax = horizontal + x * stride;
    const int* ay = vertical + y * stride;
    int sum[3] = {1 << 21, 1 << 21, 1 << 21};
    for (int j = 1; j < stride && ay[j]; ++j) {
        const int row = y0 + ay[0] + j - 1;
        int part[3] = {1 << 21, 1 << 21, 1 << 21};
        for (int i = 1; i < stride && ax[i]; ++i) {
            const int sx = ax[0] + i - 1;
            const int col = x0 + (flip ? crop_width - sx - 1 : sx);
            const uint8_t* pixel = rgb + 3 * (row * width + col);
            for (int c = 0; c < 3; ++c) part[c] += ax[i] * pixel[c];
        }
        for (int c = 0; c < 3; ++c) sum[c] += (part[c] >> 22) * ay[j];
    }
    for (int c = 0; c < 3; ++c)
        tensor[c * plane + idx] = yolo ? float(sum[c] >> 22) : __fdiv_rn(float(sum[c] >> 22), 255.f);
}

extern "C" int prepare_quality_crop(const uint8_t* rgb, int width, int left, int top,
                                    int crop_width, bool flip, const int* ax,
                                    const int* ay, int nx, int ny, bool yolo, float* tensor) {
    prepare<<<(nx * (yolo ? nx : ny) + 255) / 256, 256>>>(
        rgb, width, left, top, crop_width, flip, ax, ay, nx, ny, yolo, tensor);
    return int(cudaGetLastError());
}

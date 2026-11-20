#include "quality_crop.cu"

extern "C" int enqueue_quality_crop(const uint8_t* rgb, int x, int y, int w, bool flip,
                                    const int* ax, const int* ay, float* tensor, cudaStream_t stream) {
    prepare<<<(960 * 960 + 255) / 256, 256, 0, stream>>>(
        rgb, 2560, x, y, w, flip, ax, ay, 960, 960, false, tensor);
    return int(cudaGetLastError());
}

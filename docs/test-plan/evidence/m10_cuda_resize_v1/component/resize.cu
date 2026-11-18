// Fixed-size BGRA -> RGB960, using Pillow11.3.0's bilinear coefficient and
// two-pass 22-bit rounding rules. Derived from libImaging/Resample.c.
// Copyright (c) 1997-2011 Secret Labs AB; 1995-2011 Fredrik Lundh and contributors;
// Copyright (c) 2010 Jeffrey A. Clark and contributors.
// See third_party/pillow-11.3.0/LICENSE and provenance.json.
// No architecture-specific instructions, fast-math, GPU work or model changes.

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace {
constexpr int width = 2560, height = 1536, output = 960, precision = 22;
struct Axis {
  int stride;
  std::array<int, output> begin{}, count{};
  std::vector<int> weights;
  explicit Axis(int input) {
    const double scale = static_cast<double>(input) / output;
    stride = static_cast<int>(std::ceil(scale)) * 2 + 1;
    weights.resize(output * stride);
    std::vector<double> coefficients(stride);
    for (int xx = 0; xx < output; ++xx) {
      const double center = (xx + 0.5) * scale, ss = 1.0 / scale;
      begin[xx] = std::max(0, static_cast<int>(center - scale + 0.5));
      count[xx] = std::min(input, static_cast<int>(center + scale + 0.5)) - begin[xx];
      double total = 0;
      for (int x = 0; x < count[xx]; ++x) {
        double distance = std::abs((x + begin[xx] - center + 0.5) * ss);
        coefficients[x] = distance < 1.0 ? 1.0 - distance : 0.0;
        total += coefficients[x];
      }
      for (int x = 0; x < count[xx]; ++x) {
        coefficients[x] /= total;
        weights[xx * stride + x] = static_cast<int>(0.5 + coefficients[x] * (1 << precision));
      }
    }
  }
};
inline uint8_t rounded(int value) {
  return static_cast<uint8_t>(std::clamp(value >> precision, 0, 255));
}
}  // namespace


#include <cuda_runtime.h>
#include <cstring>
#include <memory>

namespace {
struct FlatAxis {
  int stride;
  int begin[output], count[output], weights[output*7];
};
FlatAxis flatten(const Axis& axis) {
  FlatAxis flat{};flat.stride=axis.stride;
  std::copy(axis.begin.begin(),axis.begin.end(),flat.begin);
  std::copy(axis.count.begin(),axis.count.end(),flat.count);
  std::copy(axis.weights.begin(),axis.weights.end(),flat.weights);
  return flat;
}
__device__ unsigned char round_pixel(int value) {
  const int shifted=value>>precision;
  return static_cast<unsigned char>(shifted<0?0:shifted>255?255:shifted);
}
__global__ void horizontal_pass(const unsigned char* source,unsigned char* scratch,const FlatAxis* axis) {
  const int index=blockIdx.x*blockDim.x+threadIdx.x;
  if(index>=output*height)return;
  const int yy=index/output,xx=index%output;
  const auto* row=source+yy*width*4;
  const auto* k=axis->weights+xx*axis->stride;
  int r=1<<(precision-1),g=r,b=r;
  for(int x=0;x<axis->count[xx];++x) {
    const auto* pixel=row+(x+axis->begin[xx])*4;
    r+=pixel[2]*k[x];g+=pixel[1]*k[x];b+=pixel[0]*k[x];
  }
  scratch[index*3]=round_pixel(r);scratch[index*3+1]=round_pixel(g);scratch[index*3+2]=round_pixel(b);
}
__global__ void vertical_pass(const unsigned char* scratch,unsigned char* result,const FlatAxis* axis) {
  const int index=blockIdx.x*blockDim.x+threadIdx.x;
  if(index>=output*output*3)return;
  const int yy=index/(output*3),xx=index%(output*3);
  const auto* k=axis->weights+yy*axis->stride;
  int sum=1<<(precision-1);
  for(int y=0;y<axis->count[yy];++y)sum+=scratch[(y+axis->begin[yy])*output*3+xx]*k[y];
  result[index]=round_pixel(sum);
}
struct Workspace {
  unsigned char *source=nullptr,*scratch=nullptr,*result=nullptr,*host_source=nullptr,*host_result=nullptr;
  FlatAxis *horizontal=nullptr,*vertical=nullptr;
  cudaStream_t stream=nullptr;cudaEvent_t done=nullptr;
  bool failed=false;
  ~Workspace() {
    if(stream)cudaStreamSynchronize(stream);
    if(done)cudaEventDestroy(done);
    for(void* p:{static_cast<void*>(source),static_cast<void*>(scratch),static_cast<void*>(result),
                 static_cast<void*>(horizontal),static_cast<void*>(vertical)})if(p)cudaFree(p);
    if(host_source)cudaFreeHost(host_source);
    if(host_result)cudaFreeHost(host_result);
    if(stream)cudaStreamDestroy(stream);
  }
};
constexpr size_t source_bytes=width*height*4ULL,scratch_bytes=output*height*3ULL,result_bytes=output*output*3ULL;
#define CUDA_CHECK(call) do {const auto error=(call);if(error!=cudaSuccess)return static_cast<int>(error);} while(false)
int initialize(Workspace& w) {
  int device=-1;CUDA_CHECK(cudaGetDevice(&device));if(device!=0)return 10001;
  CUDA_CHECK(cudaStreamCreateWithFlags(&w.stream,cudaStreamNonBlocking));
  CUDA_CHECK(cudaEventCreateWithFlags(&w.done,cudaEventBlockingSync|cudaEventDisableTiming));
  CUDA_CHECK(cudaMalloc(&w.source,source_bytes));CUDA_CHECK(cudaMalloc(&w.scratch,scratch_bytes));
  CUDA_CHECK(cudaMalloc(&w.result,result_bytes));CUDA_CHECK(cudaMalloc(&w.horizontal,sizeof(FlatAxis)));
  CUDA_CHECK(cudaMalloc(&w.vertical,sizeof(FlatAxis)));
  CUDA_CHECK(cudaMallocHost(&w.host_source,source_bytes));CUDA_CHECK(cudaMallocHost(&w.host_result,result_bytes));
  const auto h=flatten(Axis(width)),v=flatten(Axis(height));
  CUDA_CHECK(cudaMemcpy(w.horizontal,&h,sizeof(h),cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(w.vertical,&v,sizeof(v),cudaMemcpyHostToDevice));
  return 0;
}
int run(Workspace& w,const unsigned char* source,unsigned char* result) {
  std::memcpy(w.host_source,source,source_bytes);
  CUDA_CHECK(cudaMemcpyAsync(w.source,w.host_source,source_bytes,cudaMemcpyHostToDevice,w.stream));
  horizontal_pass<<<(output*height+255)/256,256,0,w.stream>>>(w.source,w.scratch,w.horizontal);
  CUDA_CHECK(cudaGetLastError());
  vertical_pass<<<(output*output*3+255)/256,256,0,w.stream>>>(w.scratch,w.result,w.vertical);
  CUDA_CHECK(cudaGetLastError());
  CUDA_CHECK(cudaMemcpyAsync(w.host_result,w.result,result_bytes,cudaMemcpyDeviceToHost,w.stream));
  CUDA_CHECK(cudaEventRecord(w.done,w.stream));CUDA_CHECK(cudaEventSynchronize(w.done));
  std::memcpy(result,w.host_result,result_bytes);
  return 0;
}
}
extern "C" int strata_cuda_resize_create(void** handle) noexcept {
  if(!handle)return 10001;*handle=nullptr;
  try {
    auto w=std::make_unique<Workspace>();const int code=initialize(*w);
    if(code)return code;*handle=w.release();return 0;
  } catch(...){return 10002;}
}
extern "C" int strata_cuda_resize(void* handle,const unsigned char* source,size_t length,
                                   unsigned char* result,size_t capacity) noexcept {
  if(!handle || !source || !result || length!=source_bytes || capacity!=result_bytes)return 10001;
  auto& w=*static_cast<Workspace*>(handle);if(w.failed)return 10003;
  const int code=run(w,source,result);if(code)w.failed=true;
  return code;
}
extern "C" void strata_cuda_resize_destroy(void* handle) noexcept {delete static_cast<Workspace*>(handle);}

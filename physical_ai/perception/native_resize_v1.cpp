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
constexpr int width = 3840, height = 2304, output = 960, precision = 22;
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

// Caller owns buffers; no cached mutable scratch, no retained input pointer.
// Exact sizes are checked before writing. All products/sums fit signed32 for
// nonnegative bilinear coefficients and uint8 channels (max about1.07e9).
extern "C" int strata_resize_bgra_v1(const uint8_t* source, std::size_t source_bytes,
                                     uint8_t* scratch, std::size_t scratch_bytes,
                                     uint8_t* result, std::size_t result_bytes,
                                     int threads) noexcept {
  if (!source || !scratch || !result || source_bytes != width * height * 4ULL ||
      scratch_bytes != output * height * 3ULL || result_bytes != output * output * 3ULL ||
      threads < 1 || threads > 4) return 1;
  try {
    static const Axis horizontal(width), vertical(height);
    #pragma omp parallel for num_threads(threads) schedule(static)
    for (int yy = 0; yy < height; ++yy) {
      const auto* row = source + yy * width * 4ULL;
      auto* out = scratch + yy * output * 3ULL;
      for (int xx = 0; xx < output; ++xx) {
        const auto* k = &horizontal.weights[xx * horizontal.stride];
        int r = 1 << (precision - 1), g = r, b = r;
        for (int x = 0; x < horizontal.count[xx]; ++x) {
          const auto* pixel = row + (x + horizontal.begin[xx]) * 4;
          r += pixel[2] * k[x]; g += pixel[1] * k[x]; b += pixel[0] * k[x];
        }
        out[xx * 3] = rounded(r); out[xx * 3 + 1] = rounded(g); out[xx * 3 + 2] = rounded(b);
      }
    }
    #pragma omp parallel for num_threads(threads) schedule(static)
    for (int yy = 0; yy < output; ++yy) {
      const auto* k = &vertical.weights[yy * vertical.stride];
      auto* out = result + yy * output * 3ULL;
      for (int xx = 0; xx < output * 3; ++xx) {
        int sum = 1 << (precision - 1);
        for (int y = 0; y < vertical.count[yy]; ++y)
          sum += scratch[(y + vertical.begin[yy]) * output * 3ULL + xx] * k[y];
        out[xx] = rounded(sum);
      }
    }
    return 0;
  } catch (...) { return 2; }
}

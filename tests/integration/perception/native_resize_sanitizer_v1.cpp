// Standalone ABI/buffer check for ASan+UBSan, without Python or a GPU.
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <vector>

extern "C" int strata_resize_bgra_v1(const uint8_t*, std::size_t, uint8_t*, std::size_t,
                                     uint8_t*, std::size_t, int) noexcept;

int main() {
  constexpr std::size_t input_size = 3840ULL * 2304 * 4;
  constexpr std::size_t scratch_size = 960ULL * 2304 * 3;
  constexpr std::size_t output_size = 960ULL * 960 * 3;
  std::vector<uint8_t> input(input_size + 32, 0xa5);
  std::vector<uint8_t> scratch(scratch_size + 32, 0xa5);
  std::vector<uint8_t> output(output_size + 32, 0xa5);
  for (std::size_t n = 0; n < input_size; n += 4) {
    input[16 + n] = 1; input[17 + n] = 2; input[18 + n] = 3; input[19 + n] = 77;
  }
  for (int threads : {1, 4}) {
    assert(strata_resize_bgra_v1(input.data() + 16, input_size, scratch.data() + 16,
           scratch_size, output.data() + 16, output_size, threads) == 0);
    for (std::size_t n = 0; n < output_size; ++n) assert(output[16 + n] == 3 - n % 3);
  }
  assert(strata_resize_bgra_v1(input.data(), input_size - 1, scratch.data(), scratch_size,
                              output.data(), output_size, 4) == 1);
  assert(strata_resize_bgra_v1(nullptr, input_size, scratch.data(), scratch_size,
                              output.data(), output_size, 4) == 1);
  for (const auto* bytes : {&input, &scratch, &output}) {
    assert(std::all_of(bytes->begin(), bytes->begin() + 16, [](auto n) { return n == 0xa5; }));
    assert(std::all_of(bytes->end() - 16, bytes->end(), [](auto n) { return n == 0xa5; }));
  }
}

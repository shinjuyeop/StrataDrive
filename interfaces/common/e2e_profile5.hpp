#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>

namespace stratadrive::e2e {

// AUTOSAR R25-11 Profile 5 Protect/Check의 C++17 구현. Config의 길이/offset은 bit 단위다.
struct P05Config {
    std::uint16_t data_id;
    std::uint16_t data_length_bits;
    std::uint16_t offset_bits;
    std::uint8_t max_delta_counter;
};

enum class P05Return : std::uint8_t { Ok, InputNull, InputWrong };
enum class P05Status : std::uint8_t {
    Ok = 0x00,
    NoNewData = 0x01,
    Error = 0x07,
    Repeated = 0x08,
    OkSomeLost = 0x20,
    WrongSequence = 0x40,
};

struct P05ProtectState {
    std::uint8_t counter{0};  // 다음 Protect에서 사용할 번호. 호출자가 수동 증가하지 않는다.
};
struct P05CheckState {
    std::uint8_t counter{0xFF};
    P05Status status{P05Status::Error};
};

void p05_protect_init(P05ProtectState& state);
void p05_check_init(P05CheckState& state);

// CRC 두 byte를 제외한 전체 data + DataID의 low/high byte를 계산한다.
std::optional<std::uint16_t> p05_crc(const P05Config& config,
                                    const std::uint8_t* data, std::size_t length);
P05Return p05_protect(const P05Config& config, P05ProtectState& state,
                      std::uint8_t* data, std::size_t length);
// nullptr + length=0은 새 데이터 없는 cycle. API 오류와 state.status를 함께 확인해야 한다.
P05Return p05_check(const P05Config& config, P05CheckState& state,
                    const std::uint8_t* data, std::size_t length);
bool p05_is_ok(P05Return result, P05Status status);

}  // namespace stratadrive::e2e

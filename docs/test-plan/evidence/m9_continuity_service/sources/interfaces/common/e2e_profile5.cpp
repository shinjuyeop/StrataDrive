#include "e2e_profile5.hpp"

namespace stratadrive::e2e {
namespace {
bool valid_config(const P05Config& config) {
    return config.data_length_bits >= 24U && config.data_length_bits <= 32768U &&
           config.data_length_bits % 8U == 0U && config.offset_bits % 8U == 0U &&
           config.offset_bits <= config.data_length_bits - 24U;
}

std::uint16_t crc_byte(std::uint16_t crc, std::uint8_t byte) {
    std::uint32_t value = crc ^ (static_cast<std::uint32_t>(byte) << 8U);
    for (unsigned int bit = 0; bit < 8U; ++bit) {
        value = ((value << 1U) ^ ((value & 0x8000U) != 0U ? 0x1021U : 0U)) & 0xFFFFU;
    }
    return static_cast<std::uint16_t>(value);
}
}  // namespace

void p05_protect_init(P05ProtectState& state) {
    state = P05ProtectState{};
}

void p05_check_init(P05CheckState& state) {
    state = P05CheckState{};
}

std::optional<std::uint16_t> p05_crc(const P05Config& config,
                                    const std::uint8_t* data, std::size_t length) {
    if (!valid_config(config) || data == nullptr || length != config.data_length_bits / 8U) {
        return std::nullopt;
    }
    const std::size_t offset = config.offset_bits / 8U;
    std::uint16_t crc = 0xFFFFU;
    for (std::size_t index = 0; index < length; ++index) {
        if (index != offset && index != offset + 1U) {
            crc = crc_byte(crc, data[index]);
        }
    }
    crc = crc_byte(crc, static_cast<std::uint8_t>(config.data_id & 0xFFU));
    return crc_byte(crc, static_cast<std::uint8_t>(config.data_id >> 8U));
}

P05Return p05_protect(const P05Config& config, P05ProtectState& state,
                      std::uint8_t* data, std::size_t length) {
    if (data == nullptr) {
        return P05Return::InputNull;
    }
    if (!valid_config(config) || length != config.data_length_bits / 8U) {
        return P05Return::InputWrong;
    }
    const std::size_t offset = config.offset_bits / 8U;
    data[offset + 2U] = state.counter;
    // 같은 조건으로 검증했으므로 CRC 계산은 여기서 값을 반환한다.
    const auto crc = *p05_crc(config, data, length);
    data[offset] = static_cast<std::uint8_t>(crc & 0xFFU);
    data[offset + 1U] = static_cast<std::uint8_t>(crc >> 8U);
    state.counter = static_cast<std::uint8_t>(static_cast<unsigned int>(state.counter) + 1U);
    return P05Return::Ok;
}

P05Return p05_check(const P05Config& config, P05CheckState& state,
                    const std::uint8_t* data, std::size_t length) {
    if (data == nullptr && length != 0U) {
        return P05Return::InputNull;
    }
    if (!valid_config(config) || (data != nullptr && length != config.data_length_bits / 8U)) {
        return P05Return::InputWrong;
    }
    if (data == nullptr) {
        state.status = P05Status::NoNewData;
        return P05Return::Ok;
    }
    const std::size_t offset = config.offset_bits / 8U;
    const auto received_crc = static_cast<std::uint16_t>(
        data[offset] | (static_cast<std::uint16_t>(data[offset + 1U]) << 8U));
    if (received_crc != *p05_crc(config, data, length)) {
        state.status = P05Status::Error;
        return P05Return::Ok;
    }
    const auto received_counter = data[offset + 2U];
    const auto delta = static_cast<std::uint8_t>(
        static_cast<unsigned int>(received_counter) + 256U - state.counter);
    if (delta > config.max_delta_counter) {
        state.status = P05Status::WrongSequence;
    } else if (delta == 0U) {
        state.status = P05Status::Repeated;
    } else if (delta == 1U) {
        state.status = P05Status::Ok;
    } else {
        state.status = P05Status::OkSomeLost;
    }
    // 규격에 따라 WrongSequence에서도 갱신한다. Application의 수용 cursor와는 별도다.
    state.counter = received_counter;
    return P05Return::Ok;
}

bool p05_is_ok(P05Return result, P05Status status) {
    return result == P05Return::Ok &&
           (status == P05Status::Ok || status == P05Status::OkSomeLost);
}

}  // namespace stratadrive::e2e

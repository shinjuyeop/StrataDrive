#include "e2e_profile5.hpp"

#include <gtest/gtest.h>

#include <array>

namespace {
using stratadrive::e2e::P05CheckState;
using stratadrive::e2e::P05Config;
using stratadrive::e2e::P05ProtectState;
using stratadrive::e2e::P05Return;
using stratadrive::e2e::P05Status;
using stratadrive::e2e::p05_check;
using stratadrive::e2e::p05_check_init;
using stratadrive::e2e::p05_crc;
using stratadrive::e2e::p05_is_ok;
using stratadrive::e2e::p05_protect;
using stratadrive::e2e::p05_protect_init;

constexpr P05Config kConfig{0x1234, 64, 0, 10};

std::array<std::uint8_t, 8> counter_fixture(std::uint8_t counter) {
    std::array<std::uint8_t, 8> data{};
    // 손실/순서 오류 주입용 test fixture만 state를 설정한다.
    P05ProtectState tx{counter};
    EXPECT_EQ(p05_protect(kConfig, tx, data.data(), data.size()), P05Return::Ok);
    return data;
}

TEST(E2eProfile5, MatchesOfficialR2511ProtocolExamples) {
    // PRS E2EProtocol 6.8.5, Table 6.27/6.28. 구현 출력으로 만든 기대값이 아니다.
    constexpr std::array<std::uint8_t, 8> expected_short{0x1C, 0xCA, 0, 0, 0, 0, 0, 0};
    std::array<std::uint8_t, 8> data{};
    P05ProtectState tx;
    EXPECT_EQ(p05_protect(kConfig, tx, data.data(), data.size()), P05Return::Ok);
    EXPECT_EQ(data, expected_short);
    EXPECT_EQ(p05_crc(kConfig, data.data(), data.size()), 0xCA1C);

    constexpr P05Config offset_config{0x1234, 128, 64, 1};
    constexpr std::array<std::uint8_t, 16> expected_offset{
        0, 0, 0, 0, 0, 0, 0, 0, 0x28, 0x91, 0, 0, 0, 0, 0, 0};
    std::array<std::uint8_t, 16> offset_data{};
    p05_protect_init(tx);
    EXPECT_EQ(p05_protect(offset_config, tx, offset_data.data(), offset_data.size()), P05Return::Ok);
    EXPECT_EQ(offset_data, expected_offset);
    EXPECT_EQ(p05_crc(offset_config, offset_data.data(), offset_data.size()), 0x9128);
}

TEST(E2eProfile5, ProtectOwnsCounterAndWraps255ToZero) {
    P05ProtectState tx;
    P05CheckState rx;
    std::array<std::uint8_t, 8> data{};
    for (unsigned int index = 0; index <= 256; ++index) {
        ASSERT_EQ(p05_protect(kConfig, tx, data.data(), data.size()), P05Return::Ok);
        EXPECT_EQ(data[2], index % 256);
        ASSERT_EQ(p05_check(kConfig, rx, data.data(), data.size()), P05Return::Ok);
        EXPECT_EQ(rx.status, P05Status::Ok) << index;
    }
    EXPECT_EQ(tx.counter, 1);
    EXPECT_EQ(rx.counter, 0);
    p05_protect_init(tx);
    p05_check_init(rx);
    EXPECT_EQ(tx.counter, 0);
    EXPECT_EQ(rx.counter, 0xFF);
    EXPECT_EQ(rx.status, P05Status::Error);
}

TEST(E2eProfile5, ClassifiesRepeatedLossAndResynchronizesWrongSequence) {
    P05CheckState rx;
    struct Step {
        std::uint8_t counter;
        P05Status expected;
    };
    const Step steps[] = {
        {0, P05Status::Ok}, {0, P05Status::Repeated},
        {3, P05Status::OkSomeLost}, {13, P05Status::OkSomeLost},
        {24, P05Status::WrongSequence}, {25, P05Status::Ok},
        {23, P05Status::WrongSequence}, {23, P05Status::Repeated},
    };
    for (const auto& step : steps) {
        const auto data = counter_fixture(step.counter);
        EXPECT_EQ(p05_check(kConfig, rx, data.data(), data.size()), P05Return::Ok);
        EXPECT_EQ(rx.status, step.expected);
        // WrongSequence라도 CRC 정상인 수신 counter로 재동기화한다.
        EXPECT_EQ(rx.counter, step.counter);
    }
}

TEST(E2eProfile5, StartupUsesCounter255WithoutSpecialFirstPacketAcceptance) {
    for (const auto counter : {0, 9, 10, 255}) {
        P05CheckState rx;
        const auto data = counter_fixture(static_cast<std::uint8_t>(counter));
        EXPECT_EQ(p05_check(kConfig, rx, data.data(), data.size()), P05Return::Ok);
        const auto expected = counter == 0 ? P05Status::Ok :
                              counter == 9 ? P05Status::OkSomeLost :
                              counter == 255 ? P05Status::Repeated : P05Status::WrongSequence;
        EXPECT_EQ(rx.status, expected);
    }
}

TEST(E2eProfile5, MissingDataAndCrcErrorsDoNotChangeCounter) {
    P05CheckState rx;
    auto data = counter_fixture(0);
    ASSERT_EQ(p05_check(kConfig, rx, data.data(), data.size()), P05Return::Ok);
    EXPECT_EQ(p05_check(kConfig, rx, nullptr, 0), P05Return::Ok);
    EXPECT_EQ(rx.status, P05Status::NoNewData);
    EXPECT_EQ(rx.counter, 0);

    data = counter_fixture(1);
    data[3] ^= 1;
    EXPECT_EQ(p05_check(kConfig, rx, data.data(), data.size()), P05Return::Ok);
    EXPECT_EQ(rx.status, P05Status::Error);
    EXPECT_EQ(rx.counter, 0);
    data = counter_fixture(1);
    auto wrong_data_id = kConfig;
    wrong_data_id.data_id = 0x1235;
    EXPECT_EQ(p05_check(wrong_data_id, rx, data.data(), data.size()), P05Return::Ok);
    EXPECT_EQ(rx.status, P05Status::Error);
    EXPECT_EQ(rx.counter, 0);
    EXPECT_EQ(p05_check(kConfig, rx, data.data(), data.size()), P05Return::Ok);
    EXPECT_EQ(rx.status, P05Status::Ok);
}

TEST(E2eProfile5, CoversDataOnBothSidesOfHeaderAndCounter) {
    constexpr P05Config config{0x1234, 64, 16, 10};
    std::array<std::uint8_t, 8> data{0x12, 0x34, 0, 0, 0, 0x56, 0x78, 0x9A};
    P05ProtectState tx;
    ASSERT_EQ(p05_protect(config, tx, data.data(), data.size()), P05Return::Ok);
    const auto crc = p05_crc(config, data.data(), data.size());
    auto without_crc = data;
    without_crc[2] = 0;
    without_crc[3] = 0;
    EXPECT_EQ(p05_crc(config, without_crc.data(), without_crc.size()), crc);
    for (std::size_t byte = 0; byte < data.size(); ++byte) {
        for (unsigned int bit = 0; bit < 8; ++bit) {
            auto corrupted = data;
            corrupted[byte] ^= static_cast<std::uint8_t>(1U << bit);
            P05CheckState rx;
            EXPECT_EQ(p05_check(config, rx, corrupted.data(), corrupted.size()), P05Return::Ok);
            EXPECT_EQ(rx.status, P05Status::Error) << byte << ':' << bit;
            EXPECT_EQ(rx.counter, 0xFF);
        }
    }
}

TEST(E2eProfile5, RejectsInvalidInputsWithoutMutatingBufferOrState) {
    const auto baseline = counter_fixture(0);
    for (const auto config : {P05Config{0x1234, 16, 0, 10},
                              P05Config{0x1234, 65, 0, 10},
                              P05Config{0x1234, 32776, 0, 10},
                              P05Config{0x1234, 64, 1, 10},
                              P05Config{0x1234, 64, 48, 10}}) {
        auto data = baseline;
        P05ProtectState tx{42};
        P05CheckState rx{41, P05Status::Ok};
        EXPECT_EQ(p05_protect(config, tx, data.data(), data.size()), P05Return::InputWrong);
        EXPECT_EQ(p05_check(config, rx, data.data(), data.size()), P05Return::InputWrong);
        EXPECT_EQ(tx.counter, 42);
        EXPECT_EQ(rx.counter, 41);
        EXPECT_EQ(rx.status, P05Status::Ok);
        EXPECT_EQ(data, baseline);
        EXPECT_FALSE(p05_crc(config, data.data(), data.size()));
    }
    auto data = baseline;
    P05ProtectState tx{42};
    P05CheckState rx{41, P05Status::Ok};
    EXPECT_EQ(p05_protect(kConfig, tx, nullptr, 8), P05Return::InputNull);
    EXPECT_EQ(p05_check(kConfig, rx, nullptr, 8), P05Return::InputNull);
    EXPECT_EQ(p05_protect(kConfig, tx, data.data(), 7), P05Return::InputWrong);
    EXPECT_EQ(p05_check(kConfig, rx, data.data(), 0), P05Return::InputWrong);
    EXPECT_EQ(p05_check(kConfig, rx, data.data(), 9), P05Return::InputWrong);
    EXPECT_FALSE(p05_crc(kConfig, nullptr, 8));
    EXPECT_FALSE(p05_crc(kConfig, data.data(), 7));
    EXPECT_EQ(data, baseline);
    EXPECT_EQ(tx.counter, 42);
    EXPECT_EQ(rx.counter, 41);
    EXPECT_EQ(rx.status, P05Status::Ok);
    EXPECT_FALSE(p05_is_ok(P05Return::InputWrong, rx.status));
}

TEST(E2eProfile5, SupportsMinimumAndMaximumConfiguredLength) {
    constexpr P05Config minimum{0x1234, 24, 0, 1};
    std::array<std::uint8_t, 3> short_data{};
    P05ProtectState tx;
    P05CheckState rx;
    EXPECT_EQ(p05_protect(minimum, tx, short_data.data(), short_data.size()), P05Return::Ok);
    EXPECT_EQ(p05_check(minimum, rx, short_data.data(), short_data.size()), P05Return::Ok);
    EXPECT_EQ(rx.status, P05Status::Ok);

    constexpr P05Config maximum{0x1234, 32768, 32744, 1};
    std::array<std::uint8_t, 4096> long_data{};
    p05_protect_init(tx);
    p05_check_init(rx);
    EXPECT_EQ(p05_protect(maximum, tx, long_data.data(), long_data.size()), P05Return::Ok);
    EXPECT_EQ(p05_check(maximum, rx, long_data.data(), long_data.size()), P05Return::Ok);
    EXPECT_EQ(rx.status, P05Status::Ok);
    EXPECT_EQ(long_data[4095], 0);
}

TEST(E2eProfile5, OkHelperRequiresSuccessfulCallAndPassingStatus) {
    for (const auto status : {P05Status::Ok, P05Status::OkSomeLost}) {
        EXPECT_TRUE(p05_is_ok(P05Return::Ok, status));
        EXPECT_FALSE(p05_is_ok(P05Return::InputNull, status));
        EXPECT_FALSE(p05_is_ok(P05Return::InputWrong, status));
    }
    for (const auto status : {P05Status::Error, P05Status::NoNewData,
                              P05Status::Repeated, P05Status::WrongSequence}) {
        EXPECT_FALSE(p05_is_ok(P05Return::Ok, status));
    }
}
}  // namespace

#include "steering_angle_codec.hpp"

#include <gtest/gtest.h>

#include <cmath>
#include <limits>

namespace {
using stratadrive::can::AngleBytes;
using stratadrive::can::decode_steering_angle;
using stratadrive::can::encode_steering_angle;
using stratadrive::can::kAngleResolutionRad;
using stratadrive::can::kAngleWireMaxRad;

TEST(SteeringAngleCodec, MatchesIndependentGoldenVectors) {
    struct Vector {
        double angle;
        AngleBytes bytes;
    };
    const Vector vectors[] = {
        {0.0, {0x00, 0x00}}, {0.1, {0xE8, 0x03}}, {-0.1, {0x18, 0xFC}},
        {3.2767, {0xFF, 0x7F}}, {-3.2767, {0x01, 0x80}},
    };
    for (const auto& vector : vectors) {
        const auto encoded = encode_steering_angle(vector.angle);
        ASSERT_TRUE(encoded.has_value());
        EXPECT_EQ(*encoded, vector.bytes);
        const auto decoded = decode_steering_angle(vector.bytes);
        ASSERT_TRUE(decoded.has_value());
        EXPECT_NEAR(*decoded, vector.angle, 1e-12);
    }
}

TEST(SteeringAngleCodec, RoundsBothDirectionsWithoutClamping) {
    EXPECT_EQ(encode_steering_angle(0.10006), (AngleBytes{0xE9, 0x03}));
    EXPECT_EQ(encode_steering_angle(-0.10006), (AngleBytes{0x17, 0xFC}));
    EXPECT_EQ(encode_steering_angle(kAngleResolutionRad / 2), (AngleBytes{0x01, 0x00}));
    EXPECT_EQ(encode_steering_angle(-kAngleResolutionRad / 2), (AngleBytes{0xFF, 0xFF}));
}

TEST(SteeringAngleCodec, RejectsNonFiniteAndOutOfRangeBeforeRounding) {
    const double infinity = std::numeric_limits<double>::infinity();
    for (double invalid : {std::numeric_limits<double>::quiet_NaN(), infinity, -infinity,
                           4.0, -4.0, std::nextafter(kAngleWireMaxRad, infinity),
                           std::nextafter(-kAngleWireMaxRad, -infinity)}) {
        EXPECT_FALSE(encode_steering_angle(invalid).has_value());
    }
}

TEST(SteeringAngleCodec, RejectsReservedCode) {
    EXPECT_FALSE(decode_steering_angle({0x00, 0x80}).has_value());
}

TEST(SteeringAngleCodec, DecodesLowByteFirst) {
    const auto decoded = decode_steering_angle({0x34, 0x12});
    ASSERT_TRUE(decoded.has_value());
    EXPECT_NEAR(*decoded, 0.466, 1e-12);
}

TEST(SteeringAngleCodec, PreservesEveryNonReservedWireCode) {
    for (std::uint32_t bits = 0; bits <= 0xFFFFU; ++bits) {
        if (bits == 0x8000U) {
            continue;
        }
        const AngleBytes bytes{static_cast<std::uint8_t>(bits & 0xFFU),
                               static_cast<std::uint8_t>(bits >> 8U)};
        const auto decoded = decode_steering_angle(bytes);
        ASSERT_TRUE(decoded.has_value()) << bits;
        const auto encoded = encode_steering_angle(*decoded);
        ASSERT_TRUE(encoded.has_value()) << bits;
        EXPECT_EQ(*encoded, bytes) << bits;
    }
}
}  // namespace

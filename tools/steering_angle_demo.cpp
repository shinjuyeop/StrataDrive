#include "steering_angle_codec.hpp"

#include <exception>
#include <iomanip>
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "사용법: steering_angle_demo <angle_rad>\n";
        return 1;
    }

    try {
        const std::string input{argv[1]};
        std::size_t consumed = 0;
        const double angle = std::stod(input, &consumed);
        if (consumed != input.size()) {
            std::cerr << "REJECT: rad 숫자만 입력하세요.\n";
            return 1;
        }
        const auto bytes = stratadrive::can::encode_steering_angle(angle);
        if (!bytes) {
            std::cerr << "REJECT: finite 값이며 wire 표현 범위 안이어야 합니다.\n";
            return 1;
        }
        const auto decoded = stratadrive::can::decode_steering_angle(*bytes);
        if (!decoded) {
            std::cerr << "REJECT: reserved raw code입니다.\n";
            return 1;
        }
        std::cout << std::setprecision(10) << "입력: " << angle << " rad\nBytes:";
        for (const auto byte : *bytes) {
            std::cout << ' ' << std::uppercase << std::hex << std::setfill('0')
                      << std::setw(2) << static_cast<unsigned int>(byte);
        }
        std::cout << std::dec << "\n복원: " << *decoded << " rad\n";
    } catch (const std::exception& error) {
        std::cerr << "REJECT: " << error.what() << '\n';
        return 1;
    }
    return 0;
}

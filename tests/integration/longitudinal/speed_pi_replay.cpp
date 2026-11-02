// Test-only line protocol. No plant, runtime session or command authority.
#include "speed_pi.hpp"

#include <cfenv>
#include <charconv>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace stratadrive::central;

template <typename T> T integer(const std::string& text) {
    T value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    if (result.ec != std::errc{} || result.ptr != text.data() + text.size()) {
        throw std::runtime_error("invalid unsigned integer");
    }
    return value;
}

bool boolean(const std::string& text) {
    if (text != "0" && text != "1") throw std::runtime_error("invalid boolean");
    return text == "1";
}

double number(const std::string& text) {
    char* end = nullptr;
    const auto value = std::strtod(text.c_str(), &end);
    // strtod preserves binary64 subnormals even when errno reports underflow.
    if (end == text.c_str() || end != text.c_str() + text.size()) throw std::runtime_error("invalid double");
    return value;
}

const char* reason_name(SpeedPIReason reason) {
    switch (reason) {
    case SpeedPIReason::Normal: return "normal";
    case SpeedPIReason::Uninitialized: return "uninitialized";
    case SpeedPIReason::Latched: return "latched";
    case SpeedPIReason::SampleTime: return "sample-time";
    case SpeedPIReason::Permission: return "permission";
    case SpeedPIReason::Target: return "target";
    case SpeedPIReason::InvalidSpeed: return "invalid-speed";
    case SpeedPIReason::Epoch: return "epoch";
    case SpeedPIReason::SourceAge: return "source-age";
    case SpeedPIReason::Identity: return "identity";
    }
    throw std::runtime_error("unknown reason");
}

template <typename T> void optional_number(const std::optional<T>& value) {
    if (value) std::cout << *value;
    else std::cout << "null";
}

void write_state(const SpeedPIState& state) {
    std::cout << "{\"epoch\":" << state.epoch << ",\"integral\":" << state.integral
              << ",\"previous\":" << state.previous_mps2 << ",\"last_ns\":";
    optional_number(state.last_ns);
    std::cout << ",\"fault\":" << state.fault << ",\"target\":";
    optional_number(state.target_mps);
    std::cout << ",\"sample\":";
    if (state.sample) {
        const auto& s = *state.sample;
        std::cout << "{\"epoch\":" << s.epoch << ",\"sequence\":" << s.sequence
                  << ",\"source_ns\":" << s.source_ns << ",\"speed_mps\":" << s.speed_mps << '}';
    } else std::cout << "null";
    std::cout << '}';
}

void emit(std::size_t index, const std::string& name, const std::string& op,
          std::optional<bool> accepted, const std::optional<SpeedPIOutput>& out, const SpeedPIState& state) {
    std::cout << "{\"index\":" << index << ",\"case\":\"" << name << "\",\"op\":\"" << op << "\",\"accepted\":";
    optional_number(accepted);
    std::cout << ",\"output\":";
    if (out) {
        std::cout << "{\"valid\":" << out->valid << ",\"reason\":\"" << reason_name(out->reason)
                  << "\",\"acceleration\":";
        optional_number(out->acceleration_mps2);
        std::cout << ",\"integral\":" << out->integral << ",\"source_ns\":" << out->source_ns << '}';
    } else std::cout << "null";
    std::cout << ",\"state\":";
    write_state(state);
    std::cout << "}\n";
}
}  // namespace

int main() {
    std::size_t index = 0;
    try {
        if (std::fegetround() != FE_TONEAREST) throw std::runtime_error("round-to-nearest required");
        std::cout.imbue(std::locale::classic());
        std::cout << std::boolalpha << std::setprecision(std::numeric_limits<double>::max_digits10);
        SpeedPI controller;
        std::string line, name;
        while (std::getline(std::cin, line)) {
            if (line.size() > 1024 || index >= 100000) throw std::runtime_error("input bound exceeded");
            std::istringstream input(line);
            std::vector<std::string> fields;
            for (std::string token; input >> token;) fields.push_back(token);
            if (fields.empty()) throw std::runtime_error("empty event");
            const auto& op = fields[0];
            std::optional<bool> accepted;
            std::optional<SpeedPIOutput> out;
            if (op == "new" && fields.size() == 2) {
                name = fields[1];
                if (name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-") != std::string::npos) {
                    throw std::runtime_error("invalid case name");
                }
                controller = SpeedPI{};
            } else if (name.empty()) throw std::runtime_error("new case required");
            else if (op == "init" && fields.size() == 2) {
                accepted = controller.initialize(integer<std::uint32_t>(fields[1]));
            } else if (op == "step" && (fields.size() == 5 || fields.size() == 9 || fields.size() == 6 || fields.size() == 10)) {
                const auto now = integer<std::uint64_t>(fields[1]);
                const auto target = number(fields[2]);
                const auto permission = boolean(fields[3]);
                const auto present = boolean(fields[4]);
                const auto expected=present?9U:5U;
                if (fields.size() != expected && fields.size() != expected+1) throw std::runtime_error("sample field count");
                std::optional<SpeedSample> speed;
                if (present) speed = SpeedSample{integer<std::uint32_t>(fields[5]), integer<std::uint64_t>(fields[6]),
                                                integer<std::uint64_t>(fields[7]), number(fields[8])};
                out = controller.step(now, target, speed, permission,fields.size()==expected+1?boolean(fields.back()):false);
            } else throw std::runtime_error("unknown or malformed event");
            emit(index++, name, op, accepted, out, controller.state());
        }
        if (std::cin.bad() || index == 0 || !std::cout) throw std::runtime_error("empty or failed stream");
    } catch (const std::exception& error) {
        std::cerr << "event " << index << ": " << error.what() << '\n';
        return 2;
    }
    return 0;
}

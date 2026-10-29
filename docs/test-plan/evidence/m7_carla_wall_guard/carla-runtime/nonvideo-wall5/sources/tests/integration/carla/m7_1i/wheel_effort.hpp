#pragma once
// Offline, test-only model law. No CARLA calls, authority, calibration approval,
// or physics integration. The stock package cannot consume this interface.
#include <array>
#include <cmath>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

namespace stratadrive::m7_effort {
using Four = std::array<double,4>; // FL, FR, RL, RR
struct BrakePoint { double pressure_pa; Four torque_nm; };
struct Definition {
    double wheelbase_m, front_track_m;
    Four steer_limit_rad, drive_limit_nm, brake_limit_nm;
    // Explicit evidence-backed table required for any future real backend.
    // Tests use synthetic knots, NEVER mkz/OEM calibration or M6's pressure gain.
    std::vector<BrakePoint> friction;
};
struct Effort {
    Four steer_right_rad{}, motor_nm{}, friction_nm{};
};
enum class Error { None, Value, Geometry, SteeringLimit, DriveLimit, PressureRange, BrakeLimit };
struct Result { Error error; std::optional<Effort> effort; };

class Mapping {
public:
    explicit Mapping(Definition definition): d_(std::move(definition)) {
        constexpr double half_pi=1.5707963267948966;
        if (!positive(d_.wheelbase_m) || !positive(d_.front_track_m) || d_.friction.size()<2)
            throw std::invalid_argument("geometry/friction evidence missing");
        for (unsigned w=0;w<4;++w) {
            if (!nonnegative(d_.steer_limit_rad[w]) || d_.steer_limit_rad[w]>=half_pi ||
                !nonnegative(d_.drive_limit_nm[w]) || !nonnegative(d_.brake_limit_nm[w]))
                throw std::invalid_argument("invalid wheel limits");
        }
        if (d_.steer_limit_rad[0]==0 || d_.steer_limit_rad[1]==0 ||
            d_.drive_limit_nm[2]==0 || d_.drive_limit_nm[3]==0 || d_.friction.front().pressure_pa!=0)
            throw std::invalid_argument("front steering/rear motor/zero pressure basis missing");
        double prior_pressure=-1;
        Four prior_torque{};
        for (const auto& knot:d_.friction) {
            if (!nonnegative(knot.pressure_pa) || knot.pressure_pa<=prior_pressure)
                throw std::invalid_argument("pressure knots not strictly increasing");
            for (unsigned w=0;w<4;++w) {
                const double t=knot.torque_nm[w];
                if (!nonnegative(t) || t<prior_torque[w] || t>d_.brake_limit_nm[w] ||
                    (knot.pressure_pa==0 && t!=0))
                    throw std::invalid_argument("invalid friction torque table");
            }
            prior_pressure=knot.pressure_pa;prior_torque=knot.torque_nm;
        }
    }
    // Called only AFTER Actual validation by a future adapter. This numerical
    // function alone does not prove that its doubles came from an Actual path.
    Result map(double left_equivalent_rad,double aggregate_drive_nm,double pressure_pa) const {
        if (!std::isfinite(left_equivalent_rad) || !std::isfinite(aggregate_drive_nm) ||
            !nonnegative(pressure_pa) || std::abs(left_equivalent_rad)>=1.5707963267948966)
            return {Error::Value,{}};
        if (pressure_pa>d_.friction.back().pressure_pa) return {Error::PressureRange,{}};
        const double tangent=std::tan(left_equivalent_rad);
        const double offset=d_.front_track_m*.5*tangent;
        const double left=d_.wheelbase_m-offset,right=d_.wheelbase_m+offset;
        if (!std::isfinite(offset) || !std::isfinite(left) || !std::isfinite(right) ||
            left<=0 || right<=0) return {Error::Geometry,{}};
        Effort e;
        // Ideal Ackermann model law. No speed filter or actuator lag here.
        // CARLA/PhysX configured basis must be verified by the future backend.
        const double numerator=d_.wheelbase_m*tangent;
        if (!std::isfinite(numerator)) return {Error::Geometry,{}};
        e.steer_right_rad[0]=-std::atan2(numerator,left);
        e.steer_right_rad[1]=-std::atan2(numerator,right);
        // Explicit ideal open differential: equal rear torques. Its conjugate
        // speed is the existing rear arithmetic mean, even when wheel speeds differ.
        // This is a proposed EV model law, NOT the stock mkz drivetrain calibration.
        e.motor_nm[2]=e.motor_nm[3]=aggregate_drive_nm*.5;
        for (std::size_t k=1;k<d_.friction.size();++k) {
            const auto& a=d_.friction[k-1];const auto& b=d_.friction[k];
            if (pressure_pa>b.pressure_pa) continue;
            const double fraction=(pressure_pa-a.pressure_pa)/(b.pressure_pa-a.pressure_pa);
            for (unsigned w=0;w<4;++w)
                e.friction_nm[w]=a.torque_nm[w]+fraction*(b.torque_nm[w]-a.torque_nm[w]);
            break;
        }
        for (unsigned w=0;w<4;++w) {
            if (std::abs(e.steer_right_rad[w])>d_.steer_limit_rad[w]) return {Error::SteeringLimit,{}};
            if (std::abs(e.motor_nm[w])>d_.drive_limit_nm[w]) return {Error::DriveLimit,{}};
            if (!nonnegative(e.friction_nm[w]) || e.friction_nm[w]>d_.brake_limit_nm[w])
                return {Error::BrakeLimit,{}};
        }
        return {Error::None,e};
    }
private:
    static bool nonnegative(double x) {return std::isfinite(x) && x>=0;}
    static bool positive(double x) {return std::isfinite(x) && x>0;}
    const Definition d_;
};
// Dimensional conversion, not an empirically fitted normalization coefficient.
// Future UE kg/cm/s backend only: torque [kg*m^2/s^2] -> [kg*cm^2/s^2].
inline std::optional<Four> torque_to_kg_cm2_s2(const Four& nm) {
    Four result{};
    for (unsigned w=0;w<4;++w) {
        result[w]=nm[w]*10000.;
        if (!std::isfinite(nm[w]) || !std::isfinite(result[w])) return {};
    }
    return result;
}
} // namespace stratadrive::m7_effort

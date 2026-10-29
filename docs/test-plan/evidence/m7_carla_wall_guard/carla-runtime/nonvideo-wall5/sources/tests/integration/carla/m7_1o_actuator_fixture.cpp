// Isolated response-model trajectory, NOT an ECU authority or an EV work model.
// Reuses the unchanged M7-1h/M6 response parameters and source acquisition APIs.
#include "steering_response.hpp"
#include "brake_pressure_response.hpp"
#include "drive_sil_plant.hpp"
#include "drive_controller.hpp"
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace stratadrive;
int main() {
  constexpr std::uint64_t ms = 1000000;
  simulation::SteeringResponse angle{{-.3, .3, .1, 1, 50*ms, 7}};
  simulation::BrakePressureResponse pressure{{1500000, 200000, 5000000, 10000000, 50*ms, 7}};
  simulation::DriveSilPlant motor{vecu::DriveControllerConfig{}.response};
  std::uint64_t now, last = 0;
  double torque, brake, steer;
  std::string kind;
  bool protecting = false;
  try {
    while (std::cin >> now >> torque >> brake >> steer >> kind) {
      if (!last) {
        if (!now || !angle.begin(now) || !pressure.begin(now)) throw std::runtime_error("begin");
        motor.begin(7, now);
        last = now;
      } else if (now != last + 10*ms) throw std::runtime_error("10ms acquisition gap");
      // Advance only the physical interval preceding this acquisition, at 1ms.
      for (; last < now; last += ms)
        if (!angle.advance(last+ms) || !pressure.advance(last+ms) || !motor.advance(last+ms, false))
          throw std::runtime_error("response advance");
      const auto a = angle.capture();
      const auto b = pressure.capture();
      const auto d = motor.capture(now);
      if (!a || !b || !d) throw std::runtime_error("acquisition");
      // New target affects future response only; never relabel it as an Actual.
      const bool protect = kind == "brake-protection";
      if (protecting && !protect && !pressure.begin(now)) throw std::runtime_error("protection release");
      protecting = protect;
      if (!angle.set_target(steer, now) ||
          !(protect ? pressure.request_protection(brake, now) : pressure.set_target(brake, now)) ||
          !motor.apply({drive::ActuationMode::Target, torque, std::nullopt, now}))
        throw std::runtime_error("target");
      std::cout << std::setprecision(17) << "{\"source_ns\":\"" << now
                << "\",\"model_epoch\":7,\"torque_nm\":" << d->torque_nm
                << ",\"pressure_pa\":" << pressure.actual_pressure_pa()
                << ",\"angle_left_rad\":" << angle.actual_angle_rad() << "}" << std::endl;
    }
    if (!std::cin.eof()) throw std::runtime_error("input parse");
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}

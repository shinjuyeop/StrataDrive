#include "demo/demo_commands.hpp"
#include "demo/demo_support.hpp"
#ifdef STRATADRIVE_LINUX_SESSION
#include "epoch_store.hpp"
#include "steering_runtime.hpp"
#include "multirate_runtime.hpp"
#include "steering_rtos_fixture.hpp"
#endif

#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>

namespace stratadrive::demo {
void usage(std::ostream& output) {
    output << "사용법:\n"
           << "  actuator_demo angle <angle_rad>\n"
           << "  actuator_demo frame <command|actual> <angle_rad|invalid>\n"
           << "  actuator_demo e2e\n"
           << "  actuator_demo receiver\n"
           << "  actuator_demo brake-pressure <pressure_pa>\n"
           << "  actuator_demo brake-frame <command|actual> <pressure_pa|invalid>\n"
           << "  actuator_demo brake-receiver\n"
           << "  actuator_demo drive-frame <command|actual> <torque_nm|invalid>\n"
           << "  actuator_demo drive-feedback\n"
           << "  actuator_demo bms-value <soc|voltage|current|temperature|power> <value>\n"
           << "  actuator_demo bms-frame <request|power-status|limits|battery|drive-limits|permission> [nominal|zero|invalid|partial]\n"
           << "  actuator_demo bms-receiver\n"
           << "  actuator_demo steering-model [normal|jam|slow|sensor-hold|sensor-invalid|transient]\n"
           << "  actuator_demo brake-model [normal|stuck-rise|slow-rise|stuck-release|slow-release|sensor-hold|sensor-invalid|transient]\n"
           << "  actuator_demo drive-model\n"
           << "  actuator_demo battery-model\n"
           << "  actuator_demo bms-control\n"
           << "  actuator_demo power-model [normal|bms-trip|weld|blocked]\n"
           << "  actuator_demo drive-gated [normal|charge-zero|permission-loss|hv-loss|speed-stale|limits-stale]\n"
           << "  actuator_demo drive-energy [normal|charge-zero|near-full|auxiliary]\n"
           << "  actuator_demo ev-power [normal|weld|current-unknown|aux-blocked]\n";
#ifdef STRATADRIVE_LINUX_SESSION
    output << "  actuator_demo epoch <init|next> <store_directory>\n";
    output << "  actuator_demo m4-async <logical|wall> <normal|normal-stop|partial-front|feedback-loss|command-loss|partial-arm|rejoin|old-epoch> <epoch_store> <new_output_directory>\n";
    output << "  actuator_demo steering-rtos-plant <normal|command-loss|corrupt|control-stall> <vcan> <inherited_channel_fd> <enable_ns> <output_directory>\n";
    output << "  actuator_demo steering-runtime <normal|overrun|stall> <new_output_directory> [trace-off]\n";
    output << "  actuator_demo multirate-runtime <normal|brake-stall|drive-stall|bms-stall|power-stall|rx-stall|rx-corrupt|feedback-replay|monitor-overrun|plant-overrun|monitor-stall|io-overrun> <vcan_interface> <new_output_directory> [trace-off] [owner-cpus=brake,drive,bms,power,rx,monitor,plant_fixture] [owner-fifo=10,10,9,10,18,20,19]\n";
#endif
}
} // namespace stratadrive::demo

int main(int argc, char** argv) {
    using namespace stratadrive::demo;
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            usage(std::cout);
            return 0;
        }
        if (argc >= 2) {
            const std::string command = argv[1];
            if (command == "angle" && argc == 3) demo_angle(argv[2]);
            else if (command == "frame" && argc == 4) demo_frame(argv[2], argv[3]);
            else if (command == "e2e" && argc == 2) demo_e2e();
            else if (command == "receiver" && argc == 2) demo_receiver();
            else if (command == "brake-pressure" && argc == 3) demo_brake_pressure(argv[2]);
            else if (command == "brake-frame" && argc == 4) demo_brake_frame(argv[2], argv[3]);
            else if (command == "brake-receiver" && argc == 2) demo_brake_receiver();
            else if (command == "drive-frame" && argc == 4) demo_drive_frame(argv[2], argv[3]);
            else if (command == "drive-feedback" && argc == 2) demo_drive_feedback();
            else if (command == "bms-value" && argc == 4) demo_bms_value(parse_bms_value_kind(argv[2]), parse_angle(argv[3]));
            else if (command == "bms-frame" && (argc == 3 || argc == 4)) demo_bms_frame(argv[2], argc == 4 ? argv[3] : "nominal");
            else if (command == "bms-receiver" && argc == 2) demo_bms_receiver();
            else if (command == "steering-model" && (argc == 2 || argc == 3)) demo_steering_model(argc == 3 ? argv[2] : "normal");
            else if (command == "brake-model" && (argc == 2 || argc == 3)) demo_brake_model(argc == 3 ? argv[2] : "normal");
            else if (command == "battery-model" && argc == 2) demo_battery_model();
            else if (command == "bms-control" && argc == 2) demo_bms_control();
            else if (command == "power-model" && (argc == 2 || argc == 3)) demo_power_model(argc == 3 ? argv[2] : "normal");
            else if (command == "drive-gated" && (argc == 2 || argc == 3)) demo_drive_gated(argc == 3 ? argv[2] : "normal");
            else if (command == "drive-energy" && (argc == 2 || argc == 3)) demo_drive_energy(argc == 3 ? argv[2] : "normal");
            else if (command == "ev-power" && (argc == 2 || argc == 3)) demo_ev_power(argc == 3 ? argv[2] : "normal");
            else if (command == "drive-model" && argc == 2) demo_drive_model();
#ifdef STRATADRIVE_LINUX_SESSION
            else if(command=="m4-async" && argc==6) demo_m4_async({argv[2],argv[3],argv[4],argv[5]});
            else if (command == "multirate-runtime" && argc >= 5 && argc <= 8) {
                stratadrive::simulation::MultirateRuntimeOptions options;
                options.scenario=argv[2]; options.interface_name=argv[3]; options.directory=argv[4];
                for(int i=5;i<argc;++i) {
                    const std::string argument=argv[i];
                    if(argument=="trace-off" && options.detailed_trace) options.detailed_trace=false;
                    else if(argument.rfind("owner-cpus=",0)==0 && !options.owner_cpus)
                        options.owner_cpus=stratadrive::simulation::parse_runtime_owner_cpus(argument.substr(11));
                    else if(argument.rfind("owner-fifo=",0)==0 && !options.owner_fifo_priorities)
                        options.owner_fifo_priorities=stratadrive::simulation::parse_runtime_owner_fifo(argument.substr(11));
                    else throw std::invalid_argument("unknown or duplicate runtime option");
                }
                stratadrive::simulation::run_multirate_runtime(options);
                std::cout << "RUNTIME_TRACE " << argv[4] << '\n';
            }
            else if (command == "steering-rtos-plant" && argc == 7) {
                stratadrive::simulation::run_steering_rtos_plant({argv[2],argv[3],std::stoi(argv[4]),std::stoull(argv[5]),argv[6]});
            }
            else if (command == "steering-runtime" && (argc == 4 || argc == 5)) {
                if(argc==5 && std::string(argv[4])!="trace-off") throw std::invalid_argument("expected trace-off");
                stratadrive::simulation::run_steering_runtime(argv[2],argv[3],argc==4);
                std::cout << "RUNTIME_TRACE " << argv[3] << '\n';
            }
            else if (command == "epoch" && argc == 4) {
                const std::string action = argv[2];
                if (action == "init") { stratadrive::session::EpochStore::initialize(argv[3]); std::cout << "EPOCH_STORE_INITIALIZED\n"; }
                else if (action == "next") std::cout << "EPOCH value=" << stratadrive::session::EpochStore(argv[3]).issue() << '\n';
                else throw std::invalid_argument("epoch action must be init or next");
            }
#endif
            else {
                usage(std::cerr);
                return 1;
            }
        } else {
            usage(std::cerr);
            return 1;
        }
    } catch (const std::exception& error) {
        std::cerr << "REJECT: " << error.what() << '\n';
        return 1;
    }
    return 0;
}

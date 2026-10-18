#ifndef STRATADRIVE_TRAMPOLINE_PILOT_BRIDGE_H
#define STRATADRIVE_TRAMPOLINE_PILOT_BRIDGE_H
#include <stdint.h>

/* Private same-Host fixture channel. CAN Command/Actual retain their existing wire format. */
struct PilotSensor { uint32_t magic, model_epoch; uint64_t sequence, source_ns; double angle_rad; };
struct PilotOutput { uint64_t issued_ns, deadline_ns, job; uint32_t hold, reason; double target_rad; };
#define PILOT_SENSOR_MAGIC UINT32_C(0x53545241)
#ifdef __cplusplus
extern "C" {
#endif
int pilot_open(int argc, char **argv);
void pilot_started(void);
int pilot_release(void);
void pilot_receive(void);
int pilot_control_begin(void);
void pilot_control_finish(void);
int pilot_suspend(void);
void pilot_resume(void);
void pilot_watch(void);
int pilot_done(void);
void pilot_os_error(unsigned error);
void pilot_close(unsigned error);
#ifdef __cplusplus
}
#endif
#endif

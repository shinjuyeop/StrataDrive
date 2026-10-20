#ifndef STRATADRIVE_PROBE_CHANNEL_H
#define STRATADRIVE_PROBE_CHANNEL_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// M4 candidate probe, not an ECU adapter. All calls have one application owner;
// middleware callback copies into a bounded queue and never invokes a controller.
bool probe_open(bool central);
bool probe_send(const uint8_t* bytes,uint32_t size);
uint32_t probe_take(uint8_t* bytes);
uint64_t probe_overflow(void);
void probe_close(void);
#ifdef __cplusplus
}
#endif
#endif

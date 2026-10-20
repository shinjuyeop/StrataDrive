/* Diagnostic only, not a replacement DDS atomic implementation or GC proof.
 * Compare the exact vendor helpers with an explicit C11 handoff and a
 * deliberately racy positive control. No TSan annotations or suppressions.
 */
#include <dds/ddsrt/atomics.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

static ddsrt_atomic_uint32_t vendor_ready = DDSRT_ATOMIC_UINT32_INIT(0);
static atomic_uint c11_ready;
static volatile unsigned racy_ready;
static int payload;
static int mode;

static void *publish(void *unused) {
    (void)unused;
    payload = 42;
    if (mode == 0) {
        ddsrt_atomic_fence_rel();
        ddsrt_atomic_st32(&vendor_ready, 1);
    } else if (mode == 1) {
        atomic_store_explicit(&c11_ready, 1, memory_order_release);
    } else {
        racy_ready = 1;
    }
    return NULL;
}

static void *consume(void *unused) {
    (void)unused;
    if (mode == 0) {
        while (!ddsrt_atomic_ld32(&vendor_ready)) {}
        ddsrt_atomic_fence_acq();
    } else if (mode == 1) {
        while (!atomic_load_explicit(&c11_ready, memory_order_acquire)) {}
    } else {
        while (!racy_ready) {}
    }
    printf("payload=%d\n", payload);
    return NULL;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "vendor")) mode = 0;
    else if (!strcmp(argv[1], "c11-control")) mode = 1;
    else if (!strcmp(argv[1], "race-control")) mode = 2;
    else return 2;
    pthread_t reader, writer;
    if (pthread_create(&reader, NULL, consume, NULL)) return 2;
    if (pthread_create(&writer, NULL, publish, NULL)) return 2;
    if (pthread_join(reader, NULL) || pthread_join(writer, NULL)) return 2;
    return payload == 42 ? 0 : 1;
}

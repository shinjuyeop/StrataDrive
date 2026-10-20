/* Diagnostic for the pinned CycloneDDS 11.0.1 private ABI, not an adapter.
 * The real entity-index/GC protocol owns the writer; no replacement atomics or
 * sanitizer annotations are introduced. --use-after-asleep is an ASan control.
 */
#define _POSIX_C_SOURCE 200809L
#include <dds/dds.h>
#include <dds/ddsrt/heap.h>
#include <dds/ddsrt/sync.h>
#include <dds/ddsi/ddsi_entity_index.h>
#include <dds/ddsi/ddsi_domaingv.h>
#include "dds__entity.h"
#include "packet.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static _Atomic uintptr_t watched;
static _Atomic uint64_t freed_ns;
static _Atomic int held, freed_held;
static uint64_t now_ns(void) {
    struct timespec t; assert(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;
}
static void observed_free(void *p) {
    uintptr_t expected = (uintptr_t)p;
    if (p && atomic_compare_exchange_strong_explicit(&watched, &expected, 0,
            memory_order_relaxed, memory_order_relaxed)) {
        atomic_store_explicit(&freed_held, atomic_load_explicit(&held, memory_order_relaxed), memory_order_relaxed);
        atomic_store_explicit(&freed_ns, now_ns(), memory_order_relaxed);
    }
    free(p);
}
struct context {
    struct ddsi_domaingv *gv;
    ddsi_guid_t guid;
    _Atomic int phase;
    bool violate;
    dds_entity_t writer;
    uint64_t delete_ns, deleted_ns;
    uint64_t acquired_ns, last_access_ns, scope_end_ns;
    unsigned reads;
};
static void wait_phase(struct context *c, int minimum) {
    const uint64_t until = now_ns()+2000000000u;
    while (atomic_load_explicit(&c->phase, memory_order_relaxed) < minimum) {
        assert(now_ns() < until); dds_sleepfor(DDS_USECS(100));
    }
}
static void wait_free(void) {
    const uint64_t until = now_ns()+2000000000u;
    while (!atomic_load_explicit(&freed_ns, memory_order_relaxed)) {
        assert(now_ns() < until); dds_sleepfor(DDS_USECS(100));
    }
}
static void *reader(void *arg) {
    struct context *c = arg;
    struct ddsi_thread_state *ts = ddsi_lookup_thread_state();
    ddsi_thread_state_awake(ts, c->gv);
    struct ddsi_writer *wr = ddsi_entidx_lookup_writer_guid(c->gv->entity_index, &c->guid);
    assert(wr);
    atomic_store_explicit(&watched, (uintptr_t)wr, memory_order_relaxed);
    atomic_store_explicit(&held, 1, memory_order_relaxed);
    c->acquired_ns = now_ns();
    atomic_store_explicit(&c->phase, 1, memory_order_relaxed);
    wait_phase(c, 2); /* A separate deleter has started dds_delete. */
    const uint64_t unlink_limit = now_ns()+2000000000u;
    while (ddsi_entidx_lookup_writer_guid(c->gv->entity_index, &c->guid)) {
        assert(now_ns() < unlink_limit); dds_sleepfor(DDS_USECS(100));
    }
    if (c->violate) {
        atomic_store_explicit(&held, 0, memory_order_relaxed);
        ddsi_thread_state_asleep(ts);
        c->scope_end_ns = now_ns();
        wait_free();
        dds_sleepfor(DDS_MSECS(1));
        /* Deliberately illegal: lookup result retained past quiescence. */
        volatile uint32_t invalid = *(volatile uint32_t *)&wr->e.guid;
        (void)invalid;
        abort(); /* An ASan run must diagnose the access, not reach here. */
    }
    const uint64_t until = now_ns()+20000000u;
    do {
        ddsrt_mutex_lock(&wr->e.lock);
        assert(memcmp(&wr->e.guid, &c->guid, sizeof(c->guid)) == 0);
        ddsrt_mutex_unlock(&wr->e.lock);
        c->last_access_ns = now_ns(); ++c->reads;
        assert(!atomic_load_explicit(&freed_ns, memory_order_relaxed));
        dds_sleepfor(DDS_USECS(100));
    } while (now_ns() < until);
    atomic_store_explicit(&held, 0, memory_order_relaxed);
    c->scope_end_ns = now_ns();
    ddsi_thread_state_asleep(ts);
    return NULL;
}
static void *deleter(void *arg) {
    struct context *c = arg;
    c->delete_ns = now_ns();
    atomic_store_explicit(&c->phase, 2, memory_order_relaxed);
    /* dds_delete waits for the GC status callback; it cannot release our reader. */
    assert(dds_delete(c->writer) == DDS_RETCODE_OK);
    c->deleted_ns = now_ns();
    return NULL;
}
int main(int argc, char **argv) {
    const bool violate = argc == 2 && strcmp(argv[1], "--use-after-asleep") == 0;
    assert(argc == 1 || violate);
    /* Install once before DDS creates threads; libc allocation semantics stay. */
    ddsrt_set_allocator((ddsrt_allocation_ops_t){malloc, calloc, realloc, observed_free});
    const dds_entity_t pp = dds_create_participant(51, NULL, NULL); assert(pp > 0);
    const dds_entity_t topic = dds_create_topic(pp, &strata_Packet_desc, "sd_lifetime", NULL, NULL); assert(topic > 0);
    const dds_entity_t writer = dds_create_writer(pp, topic, NULL, NULL); assert(writer > 0);
    dds_entity *entity;
    assert(dds_entity_pin(writer, &entity) == DDS_RETCODE_OK);
    struct context c = {.gv = &entity->m_domain->gv, .guid = ((dds_writer *)entity)->m_wr->e.guid,
                        .violate = violate, .writer = writer};
    dds_entity_unpin(entity);
    pthread_t thread; assert(pthread_create(&thread, NULL, reader, &c) == 0);
    wait_phase(&c, 1);
    pthread_t deletion; assert(pthread_create(&deletion, NULL, deleter, &c) == 0);
    /* Wait before pthread_join, so join does not manufacture a GC HB edge. */
    wait_free();
    assert(pthread_join(thread, NULL) == 0);
    assert(pthread_join(deletion, NULL) == 0);
    const uint64_t free_ns = atomic_load_explicit(&freed_ns, memory_order_relaxed);
    assert(!atomic_load_explicit(&freed_held, memory_order_relaxed));
    assert(c.reads && c.delete_ns < c.last_access_ns && c.last_access_ns <= c.scope_end_ns && c.scope_end_ns <= free_ns);
    assert(c.scope_end_ns <= c.deleted_ns);
    assert(dds_delete(pp) == DDS_RETCODE_OK); /* DDS joins its own GC/network threads. */
    printf("{\"delete_ns\":%llu,\"deleted_ns\":%llu,\"acquired_ns\":%llu,\"last_access_ns\":%llu,"
           "\"scope_end_ns\":%llu,\"free_ns\":%llu,\"reads\":%u,\"free_held\":0}\n",
           (unsigned long long)c.delete_ns, (unsigned long long)c.deleted_ns, (unsigned long long)c.acquired_ns,
           (unsigned long long)c.last_access_ns, (unsigned long long)c.scope_end_ns, (unsigned long long)free_ns, c.reads);
    return 0;
}

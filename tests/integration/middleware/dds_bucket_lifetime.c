/* Private-ABI diagnostic for unchanged CycloneDDS 11.0.1. Real entity-index
 * resize and real gc_buckets_cb, not a replacement hash or reclamation model. */
#define _POSIX_C_SOURCE 200809L
#include <dds/dds.h>
#include <dds/ddsrt/heap.h>
#include <dds/ddsi/ddsi_entity_index.h>
#include "dds__entity.h"
#include "packet.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static _Atomic uintptr_t watched;
static _Atomic uint64_t freed_ns;
static _Atomic int held, freed_held, phase;
static uint64_t now_ns(void) {struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return (uint64_t)t.tv_sec*1000000000u+t.tv_nsec;}
static void observed_free(void *p) {
    uintptr_t expected=(uintptr_t)p;
    if(p && atomic_compare_exchange_strong_explicit(&watched,&expected,0,memory_order_relaxed,memory_order_relaxed)) {
        atomic_store_explicit(&freed_held,atomic_load_explicit(&held,memory_order_relaxed),memory_order_relaxed);
        atomic_store_explicit(&freed_ns,now_ns(),memory_order_relaxed);
    }
    free(p);
}
static struct ddsi_domaingv *gv;
static dds_entity_t pp,topic,writers[128];
static void *buckets(void) {
    /* Reviewed private first fields: entity_index.guid_hash, chh.buckets. */
    void *hash;memcpy(&hash,gv->entity_index,sizeof(hash));
    return ddsrt_atomic_ldvoidp((ddsrt_atomic_voidp_t *)hash);
}
static void *grow(void *unused) {
    (void)unused;
    for(unsigned i=0;i<128;++i){writers[i]=dds_create_writer(pp,topic,NULL,NULL);assert(writers[i]>0);}
    atomic_store_explicit(&phase,1,memory_order_relaxed);return NULL;
}
int main(void) {
    ddsrt_set_allocator((ddsrt_allocation_ops_t){malloc,calloc,realloc,observed_free});
    pp=dds_create_participant(52,NULL,NULL);assert(pp>0);
    topic=dds_create_topic(pp,&strata_Packet_desc,"sd_buckets",NULL,NULL);assert(topic>0);
    dds_entity_t anchor=dds_create_writer(pp,topic,NULL,NULL);assert(anchor>0);
    dds_entity *entity;assert(dds_entity_pin(anchor,&entity)==0);
    gv=&entity->m_domain->gv;ddsi_guid_t guid=((dds_writer *)entity)->m_wr->e.guid;dds_entity_unpin(entity);
    struct ddsi_thread_state *ts=ddsi_lookup_thread_state();ddsi_thread_state_awake(ts,gv);
    void *old=buckets();const uint32_t size=*(uint32_t *)old;
    atomic_store_explicit(&watched,(uintptr_t)old,memory_order_relaxed);
    atomic_store_explicit(&held,1,memory_order_relaxed);
    const uint64_t acquired=now_ns();
    pthread_t creator;assert(!pthread_create(&creator,NULL,grow,NULL));
    const uint64_t limit=now_ns()+5000000000u;
    while(!atomic_load_explicit(&phase,memory_order_relaxed)) {assert(now_ns()<limit);dds_sleepfor(DDS_USECS(100));}
    void *replacement=buckets();assert(replacement!=old);
    uint64_t last=0;unsigned lookups=0;
    for(unsigned i=0;i<100;++i) {
        assert(*(uint32_t *)old==size);assert(ddsi_entidx_lookup_writer_guid(gv->entity_index,&guid));
        assert(!atomic_load_explicit(&freed_ns,memory_order_relaxed));last=now_ns();++lookups;dds_sleepfor(DDS_USECS(100));
    }
    atomic_store_explicit(&held,0,memory_order_relaxed);const uint64_t end=now_ns();ddsi_thread_state_asleep(ts);
    while(!atomic_load_explicit(&freed_ns,memory_order_relaxed)){assert(now_ns()<limit);dds_sleepfor(DDS_USECS(100));}
    assert(!pthread_join(creator,NULL));
    const uint64_t freed=atomic_load_explicit(&freed_ns,memory_order_relaxed);
    assert(last<=end && end<=freed && !atomic_load_explicit(&freed_held,memory_order_relaxed));
    printf("{\"old_bucket\":\"%p\",\"new_bucket\":\"%p\",\"old_size\":%u,\"acquired_ns\":%llu,\"last_access_ns\":%llu,\"scope_end_ns\":%llu,\"free_ns\":%llu,\"lookups\":%u,\"free_held\":0}\n",old,replacement,size,(unsigned long long)acquired,(unsigned long long)last,(unsigned long long)end,(unsigned long long)freed,lookups);
    assert(dds_delete(pp)==0);return 0;
}

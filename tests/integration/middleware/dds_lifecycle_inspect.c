/* Keep SDK C-private headers out of the C++ transport diagnostic. */
#define _POSIX_C_SOURCE 200809L
#include <dds/dds.h>
#include <dds/ddsi/ddsi_entity_index.h>
#include <dds/ddsi/ddsi_whc.h>
#include "dds__entity.h"
#include <stdint.h>
#include <assert.h>
void lifecycle_snapshot(dds_entity_t writer,uint64_t out[6]) {
    dds_entity *entity;assert(dds_entity_pin(writer,&entity)==0);
    struct ddsi_writer *wr=((dds_writer *)entity)->m_wr;
    struct ddsi_thread_state *ts=ddsi_lookup_thread_state();ddsi_thread_state_awake(ts,&entity->m_domain->gv);
    ddsrt_mutex_lock(&wr->e.lock);struct ddsi_whc_state state;wr->whc->ops->get_state(wr->whc,&state);
    out[0]=(uintptr_t)wr;out[1]=(uintptr_t)wr->whc;out[2]=wr->seq;
    out[3]=state.min_seq;out[4]=state.max_seq;out[5]=state.unacked_bytes;
    ddsrt_mutex_unlock(&wr->e.lock);ddsi_thread_state_asleep(ts);dds_entity_unpin(entity);
}

#include <dds/ddsrt/hopscotch.h>
#include <dds/ddsrt/endian.h>
#include <dds/ddsi/ddsi_lease.h>
#include <dds/ddsi/ddsi_proxy_participant.h>
#include <string.h>
#include <time.h>
/* Exact pinned vendor lookup is compiled as a diagnostic object because the
 * shared library hides this function. The entity/index/GC objects remain SDK-owned. */
int lifecycle_proxy_snapshot(dds_entity_t reader,uint64_t out[9]) {
    dds_instance_handle_t handle;
    if(dds_get_matched_publications(reader,&handle,1)<=0)return 0;
    dds_builtintopic_endpoint_t *data=dds_get_matched_publication_data(reader,handle);
    if(!data)return 0;
    struct ddsi_entity_common key={0};memcpy(&key.guid,data->key.v,sizeof(key.guid));
    for(unsigned i=0;i<3;++i)key.guid.prefix.u[i]=ddsrt_fromBE4u(key.guid.prefix.u[i]);
    key.guid.entityid.u=ddsrt_fromBE4u(key.guid.entityid.u);dds_builtintopic_free_endpoint(data);
    dds_entity *entity;if(dds_entity_pin(reader,&entity)!=0)return 0;
    struct ddsi_domaingv *gv=&entity->m_domain->gv;
    struct ddsi_thread_state *ts=ddsi_lookup_thread_state();ddsi_thread_state_awake(ts,gv);
    struct ddsrt_chh *hash;memcpy(&hash,gv->entity_index,sizeof(hash));
    struct ddsi_proxy_writer *pwr=ddsrt_chh_lookup(hash,&key);
    if(!pwr){ddsi_thread_state_asleep(ts);dds_entity_unpin(entity);return 0;}
    assert(pwr->e.kind==DDSI_EK_PROXY_WRITER);
    ddsrt_mutex_lock(&pwr->e.lock);
    struct ddsi_proxy_participant *pp=pwr->c.proxypp;
    struct ddsi_lease *lease=ddsrt_atomic_ldvoidp(&pp->minl_auto);
    out[0]=(uintptr_t)pwr;out[1]=(uintptr_t)pp;out[2]=(uintptr_t)lease;out[3]=(uintptr_t)&pwr->e.lock;
    out[4]=pwr->e.guid.prefix.u[0];out[5]=pwr->e.guid.entityid.u;
    out[6]=lease?(uint64_t)lease->tdur:0;
    struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));out[7]=(uint64_t)t.tv_sec*1000000000u+t.tv_nsec;
    ddsrt_mutex_unlock(&pwr->e.lock);
    assert(!clock_gettime(CLOCK_MONOTONIC,&t));out[8]=(uint64_t)t.tv_sec*1000000000u+t.tv_nsec;
    ddsi_thread_state_asleep(ts);dds_entity_unpin(entity);return 1;
}

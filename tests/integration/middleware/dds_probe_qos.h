#ifndef STRATADRIVE_DDS_PROBE_QOS_H
#define STRATADRIVE_DDS_PROBE_QOS_H
#include <dds/dds.h>

/* Public readback shared by the two optional diagnostics, not production QoS. */
typedef struct probe_qos_readback {
    dds_history_kind_t history;
    dds_reliability_kind_t reliability;
    dds_durability_kind_t durability;
    dds_duration_t blocking;
    int32_t depth, samples, instances, per_instance;
} probe_qos_readback;

static inline bool probe_read_qos(dds_entity_t entity, probe_qos_readback* value) {
    dds_qos_t* q=dds_create_qos();
    const bool read=dds_get_qos(entity,q)==DDS_RETCODE_OK &&
        dds_qget_history(q,&value->history,&value->depth) &&
        dds_qget_reliability(q,&value->reliability,&value->blocking) &&
        dds_qget_durability(q,&value->durability) &&
        dds_qget_resource_limits(q,&value->samples,&value->instances,&value->per_instance);
    dds_delete_qos(q);
    return read;
}
static inline bool probe_qos_matches(const probe_qos_readback* v) {
    /* KEEP_ALL depth is ignored by DDS; it is not a queue capacity. */
    return v->history==DDS_HISTORY_KEEP_ALL && v->reliability==DDS_RELIABILITY_RELIABLE &&
        v->blocking==0 && v->durability==DDS_DURABILITY_VOLATILE &&
        v->samples==8 && v->instances==1 && v->per_instance==8;
}
#endif

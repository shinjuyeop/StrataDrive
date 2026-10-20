#include "channel.h"
#include "packet.h"
#include <dds/dds.h>
#include <string.h>
static dds_entity_t participant,writer,reader;
static uint64_t failures;
bool probe_open(bool central) {
    participant=dds_create_participant(37,NULL,NULL);if(participant<0)return false;
    const dds_entity_t up=dds_create_topic(participant,&strata_Packet_desc,"sd_owner_up",NULL,NULL);
    const dds_entity_t down=dds_create_topic(participant,&strata_Packet_desc,"sd_owner_down",NULL,NULL);
    if(up<0 || down<0)return false;
    dds_qos_t* q=dds_create_qos();dds_qset_reliability(q,DDS_RELIABILITY_RELIABLE,0);
    dds_qset_history(q,DDS_HISTORY_KEEP_ALL,8);dds_qset_resource_limits(q,8,1,8);dds_qset_durability(q,DDS_DURABILITY_VOLATILE);
    writer=dds_create_writer(participant,central?down:up,q,NULL);reader=dds_create_reader(participant,central?up:down,q,NULL);
    dds_delete_qos(q);return writer>0 && reader>0;
}
bool probe_send(const uint8_t* bytes,uint32_t size) {
    if(size>512)return false;
    strata_Packet p={0};p.size=size;memcpy(p.data,bytes,size);
    const bool ok=dds_write(writer,&p)==DDS_RETCODE_OK;if(!ok)++failures;return ok;
}
uint32_t probe_take(uint8_t* bytes) {
    strata_Packet p={0};void* samples[1]={&p};dds_sample_info_t info[1];
    const dds_return_t n=dds_take(reader,samples,info,1,1);
    if(n<0){++failures;return 0;}if(n==0 || !info[0].valid_data)return 0;
    if(p.size>512){++failures;return 0;}memcpy(bytes,p.data,p.size);return p.size;
}
uint64_t probe_overflow(void){return failures;}
void probe_close(void){if(participant>0)dds_delete(participant);}

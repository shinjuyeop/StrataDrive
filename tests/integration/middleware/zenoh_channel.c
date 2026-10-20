#include "channel.h"
#include <zenoh.h>
#include <pthread.h>
#include <string.h>
static z_owned_session_t session;
static z_owned_publisher_t pub;
static z_owned_subscriber_t sub;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static uint8_t queue[8][512];static uint32_t sizes[8];static unsigned count,head;static uint64_t failures;
static bool session_open,pub_open,sub_open;
static void sample(z_loaned_sample_t* s,void* context) {
    (void)context;const z_loaned_bytes_t* payload=z_sample_payload(s);const size_t n=z_bytes_len(payload);
    pthread_mutex_lock(&lock);
    if(n>512 || count==8)++failures;
    else {const unsigned i=(head+count)%8;z_bytes_reader_t r=z_bytes_get_reader(payload);
        if(z_bytes_reader_read(&r,queue[i],n)!=n)++failures;else {sizes[i]=(uint32_t)n;++count;}}
    pthread_mutex_unlock(&lock);
}
bool probe_open(bool central) {
    z_owned_config_t config;z_config_default(&config);
    if(zc_config_insert_json5(z_loan_mut(config),"mode","\"peer\"")<0 ||
       zc_config_insert_json5(z_loan_mut(config),"scouting/multicast/enabled","false")<0 ||
       zc_config_insert_json5(z_loan_mut(config),central?"listen/endpoints":"connect/endpoints",central?"[\"tcp/10.88.0.1:7447\"]":"[\"tcp/10.88.0.1:7447\"]")<0){z_drop(z_move(config));return false;}
    if(z_open(&session,z_move(config),NULL)<0)return false;
    session_open=true;
    z_view_keyexpr_t tx,rx;z_view_keyexpr_from_str(&tx,central?"strata/down":"strata/up");z_view_keyexpr_from_str(&rx,central?"strata/up":"strata/down");
    z_publisher_options_t options;z_publisher_options_default(&options);options.congestion_control=Z_CONGESTION_CONTROL_DROP;
    if(z_declare_publisher(z_loan(session),&pub,z_loan(tx),&options)<0)return false;
    pub_open=true;
    z_owned_closure_sample_t callback;z_closure(&callback,sample,NULL,NULL);
    if(z_declare_subscriber(z_loan(session),&sub,z_loan(rx),z_move(callback),NULL)<0)return false;
    sub_open=true;return true;
}
bool probe_send(const uint8_t* bytes,uint32_t size) {
    z_owned_bytes_t payload;if(z_bytes_copy_from_buf(&payload,bytes,size)<0)return false;
    return z_publisher_put(z_loan(pub),z_move(payload),NULL)>=0;
}
uint32_t probe_take(uint8_t* bytes) {
    pthread_mutex_lock(&lock);uint32_t n=0;if(count){n=sizes[head];memcpy(bytes,queue[head],n);head=(head+1)%8;--count;}
    pthread_mutex_unlock(&lock);return n;
}
uint64_t probe_overflow(void){pthread_mutex_lock(&lock);const uint64_t n=failures;pthread_mutex_unlock(&lock);return n;}
void probe_close(void){if(sub_open)z_drop(z_move(sub));if(pub_open)z_drop(z_move(pub));if(session_open)z_drop(z_move(session));}

#define _GNU_SOURCE
#include <signal.h>
#include <ucontext.h>
#include <time.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <pthread.h>
static struct {uint64_t ns,ip,stack[64];} rows[150000];
static uintptr_t stack_end;static volatile sig_atomic_t count;static timer_t timer;static int enabled;
static void sample(int s,siginfo_t*i,void*v){(void)s;(void)i;int n=count;if(n>=150000)return;struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);rows[n].ns=(uint64_t)t.tv_sec*1000000000+t.tv_nsec;rows[n].ip=((ucontext_t*)v)->uc_mcontext.gregs[REG_RIP];uintptr_t sp=((ucontext_t*)v)->uc_mcontext.gregs[REG_RSP];if(sp+sizeof rows[n].stack<=stack_end)for(unsigned k=0;k<64;++k)rows[n].stack[k]=((uint64_t*)sp)[k];count=n+1;}
__attribute__((constructor))static void begin(void){const char*p=getenv("M7_PC_TRACE");if(!p)return;pthread_attr_t attr;void*base;size_t size;if(pthread_getattr_np(pthread_self(),&attr))return;pthread_attr_getstack(&attr,&base,&size);pthread_attr_destroy(&attr);stack_end=(uintptr_t)base+size;struct sigaction old;if(sigaction(SIGRTMIN+10,0,&old)||old.sa_handler!=SIG_DFL)return;struct sigaction sa={.sa_sigaction=sample,.sa_flags=SA_SIGINFO|SA_RESTART};sigemptyset(&sa.sa_mask);if(sigaction(SIGRTMIN+10,&sa,0))return;sigset_t unblock;sigemptyset(&unblock);sigaddset(&unblock,SIGRTMIN+10);sigprocmask(SIG_UNBLOCK,&unblock,0);struct sigevent e={.sigev_notify=SIGEV_THREAD_ID,.sigev_signo=SIGRTMIN+10};e._sigev_un._tid=syscall(SYS_gettid);if(timer_create(CLOCK_MONOTONIC,&e,&timer))return;struct itimerspec t={{0,500000},{0,500000}};enabled=timer_settime(timer,0,&t,0)==0;}
__attribute__((destructor))static void end(void){if(!enabled)return;timer_delete(timer);const char*p=getenv("M7_PC_TRACE");char output[4096];snprintf(output,sizeof output,"%s.%d",p,getpid());FILE*f=fopen(output,"w");if(f){fprintf(f,"now,pc\n");for(int i=0;i<count;i++){fprintf(f,"%lu,%lx",rows[i].ns,rows[i].ip);for(unsigned k=0;k<64;++k)fprintf(f,",%lx",rows[i].stack[k]);fputc(10,f);}fclose(f);}char maps[4096];snprintf(maps,sizeof maps,"%s.maps",output);FILE*in=fopen("/proc/self/maps","r");f=fopen(maps,"w");if(in&&f){while(fgets(maps,sizeof maps,in))fputs(maps,f);}if(in)fclose(in);if(f)fclose(f);}

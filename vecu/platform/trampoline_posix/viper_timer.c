/* SPDX-License-Identifier: GPL-2.0-or-later
 * StrataDrive's optional Linux ViPer timer backend. The pinned upstream
 * checkout stays unchanged. Interface: Trampoline viper/timer.h.
 */
#define _GNU_SOURCE
#include "timer.h"

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/timerfd.h>
#include <time.h>
#include <unistd.h>

#ifndef STRATADRIVE_ABSOLUTE_TIMER
#define STRATADRIVE_ABSOLUTE_TIMER 1
#endif

enum { TRACE_CAPACITY = 512 };
struct timer_sample {
    uint64_t target_ns, wake_ns, send_begin_ns, send_end_ns, skipped_periods;
    uint64_t policy, priority, cpu;
};
struct timer_trace {
    uint64_t magic, version, record_size, capacity, count, overflow, error, mode;
    uint64_t period_ns, origin_ns, pid, tid, policy, priority, cpu, timer_slack_ns;
    struct timer_sample samples[TRACE_CAPACITY];
};
_Static_assert(sizeof(struct timer_sample) == 64, "timer trace record layout");
_Static_assert(sizeof(struct timer_trace) == 128 + TRACE_CAPACITY * 64, "timer trace header layout");
_Static_assert(__atomic_always_lock_free(8, 0), "timer trace count must be lock free");

extern pid_t osek_app_pid;

static uint64_t monotonic_ns(void)
{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) _exit(EXIT_FAILURE);
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}

static void *timer_thread(void *argument)
{
    const vp_timer_param config = *(vp_timer_param *)argument;
    const long tid = syscall(SYS_gettid);
    char filename[80];
    snprintf(filename, sizeof(filename), "viper-timer-%ld.bin", tid);
    const int fd = open(filename, O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0 || ftruncate(fd, sizeof(struct timer_trace)) != 0) _exit(EXIT_FAILURE);
    struct timer_trace *trace = mmap(NULL, sizeof(*trace), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (trace == MAP_FAILED) _exit(EXIT_FAILURE);
    /* Prefault the bounded trace before the timer starts. No file I/O in a tick. */
    *trace = (struct timer_trace){0};
    trace->magic = UINT64_C(0x5354524154494d31);
    trace->version = 1;
    trace->record_size = sizeof(struct timer_sample);
    trace->capacity = TRACE_CAPACITY;
    trace->mode = STRATADRIVE_ABSOLUTE_TIMER;
    trace->pid = (uint64_t)getpid();
    trace->tid = (uint64_t)tid;
    struct sched_param priority;
    const int policy = sched_getscheduler(0);
    const long slack = prctl(PR_GET_TIMERSLACK);
    if (policy < 0 || sched_getparam(0, &priority) != 0 || slack < 0 ||
        !config.delay || config.delay > UINT64_MAX / 1000) {
        trace->error = errno ? (uint64_t)errno : EINVAL;
        return NULL;
    }
    trace->policy = (uint64_t)policy;
    trace->priority = (uint64_t)priority.sched_priority;
    trace->cpu = (uint64_t)sched_getcpu();
    trace->timer_slack_ns = (uint64_t)slack;
    const uint64_t period = config.delay * UINT64_C(1000);
    trace->period_ns = period;
    trace->origin_ns = monotonic_ns();
    uint64_t target = trace->origin_ns;
    int timer_fd = -1;
    if (STRATADRIVE_ABSOLUTE_TIMER) {
        timer_fd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC);
        const uint64_t first = target + period;
        struct itimerspec timer = {
            .it_interval = {0},
            .it_value = {(time_t)(first / 1000000000), (long)(first % 1000000000)}
        };
        if (config.type != ONE_SHOT) {
            timer.it_interval.tv_sec = (time_t)(period / 1000000000);
            timer.it_interval.tv_nsec = (long)(period % 1000000000);
        }
        if (timer_fd < 0 || timerfd_settime(timer_fd, TFD_TIMER_ABSTIME, &timer, NULL) != 0) {
            trace->error = (uint64_t)errno;
            if (timer_fd >= 0) close(timer_fd);
            munmap(trace, sizeof(*trace));
            return NULL;
        }
    }
    for (;;) {
        struct timespec remaining = {(time_t)(period / 1000000000), (long)(period % 1000000000)};
        uint64_t expirations = 1;
        int error = 0;
        if (STRATADRIVE_ABSOLUTE_TIMER) {
            ssize_t size;
            do { size = read(timer_fd, &expirations, sizeof(expirations)); } while (size < 0 && errno == EINTR);
            if (size != sizeof(expirations) || !expirations) error = size < 0 ? errno : EIO;
            target += expirations * period;
        } else {
            target = monotonic_ns() + period;
            do { error = clock_nanosleep(CLOCK_MONOTONIC, 0, &remaining, &remaining); } while (error == EINTR);
        }
        if (error) { trace->error = (uint64_t)error; break; }
        const uint64_t wake = monotonic_ns();
        const uint64_t send_begin = monotonic_ns();
        if (kill(osek_app_pid, config.sig) != 0) { trace->error = (uint64_t)errno; break; }
        const uint64_t send_end = monotonic_ns();
        const uint64_t skipped = STRATADRIVE_ABSOLUTE_TIMER ? expirations - 1 : (send_end - target) / period;
        const uint64_t count = trace->count;
        if (count < TRACE_CAPACITY) {
            trace->samples[count] = (struct timer_sample){target, wake, send_begin, send_end, skipped,
                (uint64_t)sched_getscheduler(0), (uint64_t)priority.sched_priority, (uint64_t)sched_getcpu()};
            __atomic_store_n(&trace->count, count + 1, __ATOMIC_RELEASE);
        } else {
            trace->overflow++;
        }
        if (config.type == ONE_SHOT) break;
        /* Send one signal, record elapsed periods, and keep the original phase.
         * Never burst old interrupts or silently claim the skipped OS ticks ran. */
    }
    if (timer_fd >= 0) close(timer_fd);
    munmap(trace, sizeof(*trace));
    return NULL;
}

vp_timer *vp_create_timer(int type, useconds_t delay, int sig)
{
    vp_timer *timer = malloc(sizeof(*timer));
    if (timer) timer->tm = (vp_timer_param){type, delay, sig};
    return timer;
}

int vp_start_timer(vp_timer *timer)
{
    return timer ? pthread_create(&timer->th, NULL, timer_thread, &timer->tm) : ENOMEM;
}

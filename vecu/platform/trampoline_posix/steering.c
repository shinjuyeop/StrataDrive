#include "tpl_os.h"
#include "pilot_bridge.h"

DeclareTask(Control);
DeclareEvent(Release);
DeclareEvent(Resume);
DeclareAlarm(ResumeAlarm);
DeclareResource(Mailbox);

int main(int argc, char **argv)
{
    if (!pilot_open(argc, argv)) return 1;
    StartOS(OSDEFAULTAPPMODE);
    return 0;
}

TASK(ReleaseDispatch)
{
    if (pilot_release()) SetEvent(Control, Release);
    TerminateTask();
}

TASK(Receive)
{
    GetResource(Mailbox);
    pilot_receive();
    ReleaseResource(Mailbox);
    TerminateTask();
}

TASK(Control)
{
    for (;;) {
        WaitEvent(Release);
        ClearEvent(Release);
        GetResource(Mailbox);
        const int prepared = pilot_control_begin();
        ReleaseResource(Mailbox);
        if (prepared) {
            if (pilot_suspend()) {
                /* Blocking this extended OS task leaves Receive/Watch runnable. */
                ClearEvent(Resume);
                /* One extra tick covers the phase between dispatch and suspend;
                 * the measured wall-time injection must still last >=120 ms. */
                SetRelAlarm(ResumeAlarm, 13, 0);
                WaitEvent(Resume);
                ClearEvent(Resume);
                pilot_resume();
            }
            pilot_control_finish();
        }
    }
}

TASK(Watch)
{
    pilot_watch();
    if (pilot_done()) ShutdownOS(E_OK);
    TerminateTask();
}

void ErrorHook(StatusType error) { pilot_os_error(error); }
void StartupHook(void) { pilot_started(); }
void ShutdownHook(StatusType error) { pilot_close(error); }

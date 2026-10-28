"""Unblock owner shutdown while awaiting an absent synchronous client tick.

Runs only on the game thread after the engine exit latch. No fabricated tick cue,
physics step, callback draining, or normal clock/authority change.
"""
def apply(text, replace):
    text=replace(text,'void FCarlaEngine::OnPreTick(UWorld *, ELevelTick TickType, float DeltaSeconds)',
                 'void FCarlaEngine::OnPreTick(UWorld *World, ELevelTick TickType, float DeltaSeconds)')
    anchor='''  if (TickType == ELevelTick::LEVELTICK_All)
  {

    if (bIsPrimaryServer)'''
    text=replace(text,anchor,'''  if (TickType == ELevelTick::LEVELTICK_All)
  {
    const auto CancelForExit = [&]() {
      if (!IsEngineExitRequested()) return false;
      M7NoDrive::Shutdown();
      // UWorld::Tick continues after this delegate returns. Prevent that
      // shutdown-only tail from registering another physics simulation.
      if (World) {
        World->bShouldSimulatePhysics = false;
#if WITH_EDITOR
        World->bEnableTraceCollision = false;
#endif
      }
      UE_LOG(LogCarla, Log, TEXT("M7Shutdown: cancelled tick wait; frame=%llu; physics disabled"),
        static_cast<unsigned long long>(GetFrameCounter()));
      return true;
    };
    if (CancelForExit()) return;

    if (bIsPrimaryServer)''')
    anchor='        Server.RunSome(1u);'
    if text.count(anchor)!=2:raise RuntimeError('expected primary and secondary wait pumps')
    text=text.replace(anchor,anchor+'\n        if (CancelForExit()) return;')
    text=replace(text,'void FCarlaEngine::OnPostTick(UWorld *World, ELevelTick TickType, float DeltaSeconds)\n{',
                 'void FCarlaEngine::OnPostTick(UWorld *World, ELevelTick TickType, float DeltaSeconds)\n{\n  if (IsEngineExitRequested()) return; // no receipt/snapshot for the cancelled tick')
    return text

# DXC shutdown lifetime diagnosis

The original V3 renderer shutdown hang resolves to MutexImpl::acquire,
llvm_shutdown and DllShutdown. The standalone corrected shader probe compiles
successfully. GDB then observes the function-static ManagedStaticMutex destructor
before DllShutdown calls llvm_shutdown on the same mutex. MutexImpl destructor
calls pthread_mutex_destroy and free, so that final acquisition accesses freed
storage. A successful isolated exit does not remove this lifetime defect.

The first ctypes compile prototype used the Windows COM vtable index; Linux
IUnknown has two additional virtual destructor slots. Its crash in
CreateBlobFromBlob was a probe error, not evidence of a shader compiler crash.
The corrected probe uses indices8/5/5 and successfully compiles/releases shaders.
Both failed prototype diagnostics and corrected results are retained.

The proposed source fix makes this one small synchronization object live for
process lifetime; llvm_shutdown still destroys the other ManagedStatic objects.
Build and final verification outcomes are recorded in the parent report.

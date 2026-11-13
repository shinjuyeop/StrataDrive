set pagination off
set debuginfod enabled off
set auto-solib-add off
set breakpoint pending on
break llvm::sys::MutexImpl::~MutexImpl()
commands
silent
printf "MUTEX_DESTRUCTOR\n"
bt 3
continue
end
break llvm::llvm_shutdown()
commands
silent
printf "LLVM_SHUTDOWN\n"
bt 3
continue
end
catch load libdxcompiler
commands
silent
sharedlibrary libdxcompiler
continue
end
run

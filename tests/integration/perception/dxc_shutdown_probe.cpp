// Standalone DXC lifecycle regression, no engine, camera, or control activity.
// Churn mode uses ordinary exit-handler allocations to expose the original
// library's attempt to acquire an already-destroyed ManagedStatic mutex.
#include "dxc/Support/WinAdapter.h"
#include "dxc/dxcapi.h"
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <pthread.h>

static void heap_churn() {
    for(unsigned i=0;i<64;++i) {
        auto* lock=static_cast<pthread_mutex_t*>(std::malloc(sizeof(pthread_mutex_t)));
        if(!lock || pthread_mutex_init(lock,nullptr) || pthread_mutex_lock(lock))std::abort();
        // A valid application-owned locked mutex remains alive through exit.
        // No writes through freed pointers or debugger memory injection.
    }
    std::puts("exit-allocations-complete");std::fflush(stdout);
}

int main(int argc,char** argv) {
    if(argc!=4)return 2;
    if(std::strcmp(argv[2],"churn")==0 && std::atexit(heap_churn))return 3;
    void* library=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    if(!library){std::fprintf(stderr,"%s\n",dlerror());return 4;}
    auto create=reinterpret_cast<DxcCreateInstanceProc>(dlsym(library,"DxcCreateInstance"));
    if(!create)return 5;
    IDxcLibrary* utils=nullptr;IDxcCompiler* compiler=nullptr;IDxcBlobEncoding* source=nullptr;
    IDxcOperationResult* result=nullptr;IDxcBlob* binary=nullptr;
    if(FAILED(create(CLSID_DxcLibrary,__uuidof(IDxcLibrary),reinterpret_cast<void**>(&utils))) ||
       FAILED(create(CLSID_DxcCompiler,__uuidof(IDxcCompiler),reinterpret_cast<void**>(&compiler))))return 6;
    const char* text="float4 main() : SV_Target { return float4(1,0,0,1); }";
    if(FAILED(utils->CreateBlobWithEncodingFromPinned(text,std::strlen(text),65001,&source)))return 7;
    const wchar_t* args[]={L"-spirv"};HRESULT status=0;
    if(FAILED(compiler->Compile(source,L"lifetime.hlsl",L"main",L"ps_6_0",args,1,nullptr,0,nullptr,&result)) ||
       FAILED(result->GetStatus(&status)) || FAILED(status) || FAILED(result->GetResult(&binary)))return 8;
    FILE* output=std::fopen(argv[3],"wb");if(!output)return 9;
    const auto size=binary->GetBufferSize();const bool written=std::fwrite(binary->GetBufferPointer(),1,size,output)==size;
    std::fclose(output);binary->Release();result->Release();source->Release();compiler->Release();utils->Release();
    if(!written)return 10;
    std::puts("shader-compiled-and-released");std::fflush(stdout);
    // Deliberately keep the DSO loaded until process exit, as in the failing UE
    // shutdown. Its default-priority DllShutdown runs after C++ exit handlers.
    return 0;
}

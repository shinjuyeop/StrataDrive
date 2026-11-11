// Opt-in Linux/Vulkan RGB readback experiment. Included after SceneCaptureCamera.h.
// No UObject is dereferenced by the asynchronous completion task.
#include "Async/Async.h"
#include "RHIGPUReadback.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <thread>

namespace StrataM10Readback {
using Clock = std::chrono::steady_clock;
static uint64 Now() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count();
}
static std::atomic<unsigned> Inflight{0};
static std::atomic<unsigned> Sequence{0};
static bool Enabled() {
  static const bool Value = FParse::Param(FCommandLine::Get(), TEXT("StrataM10ReadbackProfile"));
  return Value;
}
static bool Deferred() {
  static const bool Value = FParse::Param(FCommandLine::Get(), TEXT("StrataM10DeferredReadback"));
  return Value;
}
struct Dimensions {
  uint32 Width, Height;
  float Fov;
  uint32 GetImageWidth() const { return Width; }
  uint32 GetImageHeight() const { return Height; }
  float GetFOVAngle() const { return Fov; }
};
struct Trace {
  uint64 Frame, Capture, Render=0, Copy=0, Flush=0, Query=0, Worker=0, Ready=0, Lock=0, Send=0, End=0;
  double Timestamp;
  unsigned Slot, Serial;
  const char* Error="";
  void Emit() const {
    std::fprintf(stderr,
      "STRATA_READBACK_V1 {\"frame\":%llu,\"timestamp\":%.9f,\"deferred\":%s,"
      "\"serial\":%u,\"inflight\":%u,\"capture\":%llu,\"render\":%llu,\"copy\":%llu,"
      "\"flush\":%llu,\"query\":%llu,\"worker\":%llu,\"ready\":%llu,\"lock\":%llu,"
      "\"send\":%llu,\"end\":%llu,\"error\":\"%s\"}\n",
      (unsigned long long)Frame, Timestamp, Deferred()?"true":"false", Serial, Slot,
      (unsigned long long)Capture, (unsigned long long)Render, (unsigned long long)Copy,
      (unsigned long long)Flush, (unsigned long long)Query, (unsigned long long)Worker,
      (unsigned long long)Ready, (unsigned long long)Lock, (unsigned long long)Send,
      (unsigned long long)End, Error);
  }
};
static void Send(ASceneCaptureCamera& Sensor, FAsyncDataStream StreamValue) {
  check(IsInGameThread());
  if (!Sensor.HasActorBegunPlay() || Sensor.IsPendingKill()) return;
  auto T = std::make_shared<Trace>();
  T->Capture=Now(); T->Frame=FCarlaEngine::GetFrameCounter();
  T->Timestamp=Sensor.GetEpisode().GetElapsedGameTime();
  T->Serial=Sequence.fetch_add(1)+1;
  T->Slot=Inflight.fetch_add(1)+1;
  if (T->Slot>3 || T->Serial>4096) {
    --Inflight; T->Error="bounded_capacity"; T->End=Now(); T->Emit(); return;
  }
  auto Stream=std::make_shared<FAsyncDataStream>(std::move(StreamValue));
  Stream->SetFrameNumber(T->Frame);
  Stream->SetTimestamp(T->Timestamp);
  Stream->SetTransform(Sensor.GetActorTransform());
  const Dimensions D{Sensor.GetImageWidth(), Sensor.GetImageHeight(), Sensor.GetFOVAngle()};
  if (D.Width!=3840 || D.Height!=2304) {
    --Inflight; T->Error="unexpected_dimensions"; T->End=Now(); T->Emit(); return;
  }
  // CaptureScene and the immediately following copy execute in render-command order.
  // EndPlay flushes these render commands before the render target is destroyed.
  auto* Target=Sensor.GetCaptureRenderTarget();
  Sensor.EnqueueRenderSceneImmediate();
  ENQUEUE_RENDER_COMMAND(StrataM10Readback)([Target, Stream, D, T](FRHICommandListImmediate& Cmd) {
    T->Render=Now();
    auto* Resource=static_cast<const FTextureRenderTarget2DResource*>(Target->Resource);
    FTexture2DRHIRef Texture=Resource->GetRenderTargetTexture();
    if (!Texture || Texture->GetSizeXY()!=FIntPoint(D.Width,D.Height) || Texture->GetFormat()!=PF_B8G8R8A8) {
      --Inflight; T->Error="unexpected_texture"; T->End=Now(); T->Emit(); return;
    }
    auto Readback=std::make_unique<FRHIGPUTextureReadback>(TEXT("StrataM10RGBReadback"));
    Readback->EnqueueCopy(Cmd,Texture,FResolveRect(0,0,D.Width,D.Height));
    T->Copy=Now();
    if (Deferred()) {
      // Submit work and refresh fences without waiting for a query result.
      Cmd.SubmitCommandsHint();
      T->Flush=Now(); T->Query=T->Flush;
    } else {
      FRenderQueryRHIRef Query=RHICreateRenderQuery(RQT_AbsoluteTime);
      Cmd.EndRenderQuery(Query);
      Cmd.ImmediateFlush(EImmediateFlushType::FlushRHIThread);
      T->Flush=Now();
      uint64 Value=0;
      if (!Cmd.GetRenderQueryResult(Query,Value,true)) T->Error="query_failed";
      T->Query=Now();
    }
    AsyncTask(ENamedThreads::HighTaskPriority,[Stream,D,T,Readback=std::move(Readback)]() mutable {
      T->Worker=Now();
      while (!Readback->IsReady()) {
        // Same bounded poll in both variants. Never free an in-flight GPU resource.
        std::this_thread::sleep_for(std::chrono::microseconds(100));
      }
      T->Ready=Now();
      const uint32 Size=D.Width*D.Height*4;
      void* Data=Readback->Lock(Size);
      T->Lock=Now();
      if (Data) {
        auto Buffer=Stream->PopBufferFromPool();
        using Serializer=carla::sensor::s11n::ImageSerializer;
        Buffer.copy_from(Serializer::header_offset,boost::asio::buffer(Data,Size));
        carla::Buffer Ready=Serializer::Serialize(D,std::move(Buffer));
        auto View=carla::BufferView::CreateFrom(std::move(Ready));
        // Send's sensor argument is unused; D is an immutable value, never a UObject.
        auto DimensionCopy=D;
        Stream->Send(DimensionCopy,View);
      } else T->Error="null_mapping";
      T->Send=Now();
      Readback->Unlock(); Readback.reset();
      T->End=Now();
      --Inflight;
      T->Emit();
    });
  });
}
} // namespace StrataM10Readback

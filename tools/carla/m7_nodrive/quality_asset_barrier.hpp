#pragma once
#include "ComponentRecreateRenderStateContext.h"
#include "DistanceFieldAtlas.h"
#include "EngineUtils.h"
#include "ShaderCompiler.h"
#include "RenderingThread.h"
#include "Carla/Sensor/Sensor.h"
#include "Carla/Vehicle/CarlaWheeledVehicle.h"
#include "Carla/Walker/WalkerBase.h"

namespace StrataM10VisualInspect {
// Offline preparation only. No sensor, vehicle, walker, or native authority can be active.
inline bool QualityBarrier(UCarlaEpisode& Episode,const std::string& Input,bool Locked,std::string& Output) {
  if (!FParse::Param(FCommandLine::Get(),TEXT("StrataM10QualityAssetBarrier")) || Input.size()>512)
    return false;
  Json J;
  if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(UTF8_TO_TCHAR(Input.c_str())),J) || !J.IsValid())
    return false;
  FString Op,Presented;
  if(!J->TryGetStringField(TEXT("op"),Op) || Op!=TEXT("quality_asset_barrier")) return false;
  auto Result=Object();
  Result->SetBoolField(TEXT("ok"),false);
  const auto Key=FPlatformMisc::GetEnvironmentVariable(TEXT("STRATADRIVE_M10_QUALITY_KEY"));
  auto* World=Episode.GetWorld();
  if (!IsInGameThread() || Locked || Key.Len()!=64 || !J->TryGetStringField(TEXT("key"),Presented) ||
      Key!=Presented || !World || !World->GetMapName().EndsWith(TEXT("Town04_Opt")) ||
      !Episode.GetSettings().bSynchronousMode || !GDistanceFieldAsyncQueue || !GShaderCompilingManager) {
    Result->SetStringField(TEXT("reason"),TEXT("dedicated_quality_context"));
  } else if (TActorIterator<ASensor>(World) || TActorIterator<ACarlaWheeledVehicle>(World) ||
             TActorIterator<AWalkerBase>(World)) {
    Result->SetStringField(TEXT("reason"),TEXT("world_has_active_actors"));
  } else {
    FlushAsyncLoading();
    FlushRenderingCommands();
    Result->SetNumberField(TEXT("distance_tasks_before"),GDistanceFieldAsyncQueue->GetNumOutstandingTasks());
    Result->SetNumberField(TEXT("shader_jobs_before"),GShaderCompilingManager->GetNumRemainingJobs());
    {
      // Tags use their parent's mesh render data. Suspend all proxies together while
      // UE replaces derived mesh resources, then rebuild from the completed data.
      FGlobalComponentRecreateRenderStateContext ParkedRenderState;
      GDistanceFieldAsyncQueue->BlockUntilAllBuildsComplete();
      GShaderCompilingManager->FinishAllCompilation();
    }
    FlushRenderingCommands();
    const int32 Distance=GDistanceFieldAsyncQueue->GetNumOutstandingTasks();
    const int32 Shaders=GShaderCompilingManager->GetNumRemainingJobs();
    Result->SetNumberField(TEXT("distance_tasks_after"),Distance);
    Result->SetNumberField(TEXT("shader_jobs_after"),Shaders);
    Result->SetBoolField(TEXT("ok"),Distance==0 && Shaders==0);
    Result->SetStringField(TEXT("map"),World->GetMapName());
  }
  FString Text;FJsonSerializer::Serialize(Result.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));
  Output=TCHAR_TO_UTF8(*Text);
  return true;
}
}

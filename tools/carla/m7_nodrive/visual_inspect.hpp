#pragma once
// Explicit, read-only preparation probe. Never called from a physical tick and
// refused once native authority is bound. This is not a scene-admission proof.
#include "Carla/Game/CarlaEngine.h"
#include "Carla/Game/CarlaEpisode.h"
#include "Carla/Actor/CarlaActor.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/PlatformMisc.h"
#include <time.h>

namespace StrataM10VisualInspect {
using Json=TSharedPtr<FJsonObject>;
using Array=TArray<TSharedPtr<FJsonValue>>;
inline Json Object(){return MakeShared<FJsonObject>();}
inline FString Decimal(uint64 V){return FString::Printf(TEXT("%llu"),static_cast<unsigned long long>(V));}
inline uint64 Clock(){timespec T{};return clock_gettime(CLOCK_MONOTONIC,&T)==0?uint64(T.tv_sec)*1000000000+T.tv_nsec:0;}
inline Array Transform(const FTransform& T) {
  const auto P=T.GetTranslation();const auto Q=T.GetRotation();const auto S=T.GetScale3D();
  Array A;
  for(double V:{double(P.X),double(P.Y),double(P.Z),double(Q.X),double(Q.Y),double(Q.Z),double(Q.W),double(S.X),double(S.Y),double(S.Z)}) {
    A.Add(MakeShared<FJsonValueNumber>(V));
  }
  return A;
}
inline Json Parameter(const FMaterialParameterInfo& P) {
  auto J=Object();J->SetStringField(TEXT("name"),P.Name.ToString());
  J->SetNumberField(TEXT("association"),int(P.Association));J->SetNumberField(TEXT("index"),P.Index);return J;
}
inline Json Material(UMaterialInterface* M) {
  auto J=Object();if(!M){J->SetBoolField(TEXT("present"),false);return J;}
  J->SetBoolField(TEXT("present"),true);J->SetStringField(TEXT("object"),M->GetPathName());
  auto* Asset=M;
  for(unsigned Depth=0;Depth<16;++Depth) {
    auto* Dynamic=Cast<UMaterialInstanceDynamic>(Asset);if(!Dynamic)break;
    Asset=Dynamic->Parent;if(!Asset)break;
  }
  J->SetStringField(TEXT("asset"),Asset?Asset->GetPathName():TEXT(""));
  J->SetStringField(TEXT("package"),Asset?Asset->GetOutermost()->GetName():TEXT(""));
  Array Scalars,Vectors,Textures,Unsupported;TArray<FMaterialParameterInfo> Infos;TArray<FGuid> Ids;
  M->GetAllScalarParameterInfo(Infos,Ids);
  for(const auto& P:Infos){auto R=Parameter(P);float V=0;R->SetBoolField(TEXT("resolved"),M->GetScalarParameterValue(P,V));R->SetNumberField(TEXT("value"),V);Scalars.Add(MakeShared<FJsonValueObject>(R));}
  Infos.Reset();Ids.Reset();M->GetAllVectorParameterInfo(Infos,Ids);
  for(const auto& P:Infos){auto R=Parameter(P);FLinearColor V=FLinearColor::Transparent;R->SetBoolField(TEXT("resolved"),M->GetVectorParameterValue(P,V));R->SetArrayField(TEXT("value"),{MakeShared<FJsonValueNumber>(V.R),MakeShared<FJsonValueNumber>(V.G),MakeShared<FJsonValueNumber>(V.B),MakeShared<FJsonValueNumber>(V.A)});Vectors.Add(MakeShared<FJsonValueObject>(R));}
  Infos.Reset();Ids.Reset();M->GetAllTextureParameterInfo(Infos,Ids);
  for(const auto& P:Infos){auto R=Parameter(P);UTexture* V=nullptr;R->SetBoolField(TEXT("resolved"),M->GetTextureParameterValue(P,V));R->SetStringField(TEXT("value"),V?V->GetPathName():TEXT(""));R->SetStringField(TEXT("package"),V?V->GetOutermost()->GetName():TEXT(""));Textures.Add(MakeShared<FJsonValueObject>(R));}
  Infos.Reset();Ids.Reset();M->GetAllRuntimeVirtualTextureParameterInfo(Infos,Ids);
  for(const auto& P:Infos){auto R=Parameter(P);R->SetStringField(TEXT("kind"),TEXT("runtime_virtual_texture"));Unsupported.Add(MakeShared<FJsonValueObject>(R));}
  Infos.Reset();Ids.Reset();M->GetAllFontParameterInfo(Infos,Ids);
  for(const auto& P:Infos){auto R=Parameter(P);R->SetStringField(TEXT("kind"),TEXT("font"));Unsupported.Add(MakeShared<FJsonValueObject>(R));}
  J->SetArrayField(TEXT("scalars"),Scalars);J->SetArrayField(TEXT("vectors"),Vectors);
  J->SetArrayField(TEXT("textures"),Textures);J->SetArrayField(TEXT("unsupported_parameters"),Unsupported);return J;
}
inline Json Actor(UCarlaEpisode& Episode,uint32 Id) {
  auto R=Object();R->SetNumberField(TEXT("actor"),Id);
  auto* Entry=Episode.FindCarlaActor(Id);auto* A=Entry?Entry->GetActor():nullptr;
  R->SetBoolField(TEXT("present"),A!=nullptr);if(!A)return R;
  R->SetStringField(TEXT("class"),A->GetClass()->GetPathName());
  R->SetArrayField(TEXT("world_transform_cm_xyzw_scale"),Transform(A->GetActorTransform()));
  Array Components;TInlineComponentArray<USceneComponent*> All;A->GetComponents(All);
  All.Sort([](const USceneComponent& X,const USceneComponent& Y){return X.GetName()<Y.GetName();});
  for(auto* C:All) {
    auto J=Object();J->SetStringField(TEXT("name"),C->GetName());J->SetStringField(TEXT("class"),C->GetClass()->GetPathName());
    J->SetBoolField(TEXT("visible"),C->IsVisible());J->SetBoolField(TEXT("tick_enabled"),C->IsComponentTickEnabled());
    J->SetStringField(TEXT("parent"),C->GetAttachParent()?C->GetAttachParent()->GetName():TEXT(""));
    J->SetStringField(TEXT("socket"),C->GetAttachSocketName().ToString());
    J->SetArrayField(TEXT("relative_transform_cm_xyzw_scale"),Transform(C->GetRelativeTransform()));
    J->SetArrayField(TEXT("world_transform_cm_xyzw_scale"),Transform(C->GetComponentTransform()));
    if(auto* P=Cast<UPrimitiveComponent>(C))J->SetBoolField(TEXT("simulating_physics"),P->IsSimulatingPhysics());
    if(auto* M=Cast<UMeshComponent>(C)) {
      Array Materials;for(int32 I=0;I<M->GetNumMaterials();++I)Materials.Add(MakeShared<FJsonValueObject>(Material(M->GetMaterial(I))));
      J->SetArrayField(TEXT("materials"),Materials);
    }
    if(auto* Static=Cast<UStaticMeshComponent>(C)) {
      auto* Mesh=Static->GetStaticMesh();J->SetStringField(TEXT("mesh"),Mesh?Mesh->GetPathName():TEXT(""));
      J->SetStringField(TEXT("mesh_package"),Mesh?Mesh->GetOutermost()->GetName():TEXT(""));
    }
    if(auto* Skinned=Cast<USkinnedMeshComponent>(C)) {
      auto* Mesh=Skinned->SkeletalMesh;J->SetStringField(TEXT("mesh"),Mesh?Mesh->GetPathName():TEXT(""));
      J->SetStringField(TEXT("mesh_package"),Mesh?Mesh->GetOutermost()->GetName():TEXT(""));
      J->SetStringField(TEXT("master_pose"),Skinned->MasterPoseComponent.IsValid()?Skinned->MasterPoseComponent->GetName():TEXT(""));
      J->SetNumberField(TEXT("revision"),Skinned->GetBoneTransformRevisionNumber());
      J->SetNumberField(TEXT("predicted_lod"),Skinned->PredictedLODLevel);
      J->SetNumberField(TEXT("visibility_anim_tick"),int(Skinned->VisibilityBasedAnimTickOption));
      bool Parallel=false;
      if(auto* Skeletal=Cast<USkeletalMeshComponent>(Skinned)) {
        Parallel=Skeletal->IsRunningParallelEvaluation();J->SetBoolField(TEXT("parallel_evaluation"),Parallel);
        J->SetBoolField(TEXT("pose_ticked_this_frame"),Skeletal->PoseTickedThisFrame());
        J->SetBoolField(TEXT("pause_anims"),Skeletal->bPauseAnims);
        J->SetBoolField(TEXT("clothing_present"),Skeletal->GetClothingSimulation()!=nullptr);
      }
      // Never wait for an animation task or read its editable arrays.
      if(!Parallel) {
        J->SetNumberField(TEXT("active_morph_targets"),Skinned->ActiveMorphTargets.Num());
        Array Weights;for(float Weight:Skinned->MorphTargetWeights)Weights.Add(MakeShared<FJsonValueNumber>(Weight));J->SetArrayField(TEXT("morph_weights"),Weights);
        Array Bones;const auto& Poses=Skinned->GetComponentSpaceTransforms();const auto& Visible=Skinned->GetBoneVisibilityStates();
        J->SetNumberField(TEXT("declared_bones"),Skinned->GetNumBones());
        for(int32 I=0;I<Poses.Num() && I<2048;++I) {
          auto B=Object();const auto Name=Skinned->GetBoneName(I);
          B->SetStringField(TEXT("name"),Name.ToString());B->SetStringField(TEXT("parent"),Skinned->GetParentBone(Name).ToString());
          B->SetArrayField(TEXT("component_transform_cm_xyzw_scale"),Transform(Poses[I]));
          B->SetNumberField(TEXT("visibility"),Visible.IsValidIndex(I)?Visible[I]:-1);Bones.Add(MakeShared<FJsonValueObject>(B));
        }
        J->SetArrayField(TEXT("bones"),Bones);J->SetBoolField(TEXT("bones_truncated"),Poses.Num()>2048);
      }
    }
    Components.Add(MakeShared<FJsonValueObject>(J));
  }
  R->SetArrayField(TEXT("components"),Components);return R;
}
inline bool Request(UCarlaEpisode& Episode,const std::string& Input,bool NativeLocked,std::string& Output) {
  if(!FParse::Param(FCommandLine::Get(),TEXT("StrataM10VisualInspect")))return false;
  if(Input.size()>4096 || Input.find('\0')!=std::string::npos)return false;
  Json J;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(UTF8_TO_TCHAR(Input.c_str())),J)||!J.IsValid())return false;
  FString Op;if(!J->TryGetStringField(TEXT("op"),Op)||Op!=TEXT("visual_inspect"))return false;
  auto R=Object();R->SetBoolField(TEXT("ok"),false);R->SetBoolField(TEXT("complete_scene_proof"),false);
  const FString Key=FPlatformMisc::GetEnvironmentVariable(TEXT("STRATADRIVE_M10_VISUAL_INSPECT_KEY"));FString Presented;
  const TArray<TSharedPtr<FJsonValue>>* Ids=nullptr;
  if(NativeLocked)R->SetStringField(TEXT("reason"),TEXT("native_authority_already_bound"));
  else if(Key.Len()!=64 || !J->TryGetStringField(TEXT("key"),Presented) || Presented!=Key)R->SetStringField(TEXT("reason"),TEXT("probe_key"));
  else if(!J->TryGetArrayField(TEXT("actors"),Ids)||Ids->Num()<1||Ids->Num()>3)R->SetStringField(TEXT("reason"),TEXT("bounded_actor_list"));
  else {
    Array Rows;bool Valid=true;uint32 Previous=0;const auto Begin=Clock();
    for(const auto& V:*Ids){double N=0;if(!V->TryGetNumber(N)||!FMath::IsFinite(N)||N<1||N>MAX_uint32||N!=double(uint32(N))||uint32(N)<=Previous){Valid=false;break;}Previous=uint32(N);Rows.Add(MakeShared<FJsonValueObject>(Actor(Episode,Previous)));}
    R->SetBoolField(TEXT("ok"),Valid);R->SetArrayField(TEXT("actors"),Rows);
    R->SetStringField(TEXT("frame"),Decimal(FCarlaEngine::GetFrameCounter()));
    R->SetNumberField(TEXT("source_seconds"),Episode.GetElapsedGameTime());
    R->SetStringField(TEXT("acquired_begin_ns"),Decimal(Begin));R->SetStringField(TEXT("acquired_end_ns"),Decimal(Clock()));
    R->SetStringField(TEXT("scope"),TEXT("read-only preparation inspection; no completed physics binding or admission"));
  }
  FString Text;FJsonSerializer::Serialize(R.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));Output=TCHAR_TO_UTF8(*Text);return true;
}
}

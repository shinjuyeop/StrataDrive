#pragma once
#include "Carla/Vehicle/CarlaWheeledVehicle.h"
#include "VehicleAnimInstance.h"
#include "VehicleWheel.h"
#include "WheeledVehicleMovementComponent.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
namespace StrataM10VisualInspect {
inline UVehicleAnimInstance* WheelAnimation(UCarlaEpisode& Episode, uint32 Id, bool CloneOnly) {
  auto* Entry=Episode.FindCarlaActor(Id);
  auto* Vehicle=Entry ? Cast<ACarlaWheeledVehicle>(Entry->GetActor()) : nullptr;
  auto* Mesh=Vehicle ? Vehicle->GetMesh() : nullptr;
  if (!Mesh || (CloneOnly && Mesh->IsSimulatingPhysics()) || Mesh->IsRunningParallelEvaluation())
    return nullptr;
  return Cast<UVehicleAnimInstance>(Mesh->GetAnimInstance());
}
// UE exposes this static game-thread accessor to derived animation types. It
// accepts the actual animation instance, with no downcast or object creation.
struct FCompletedWheelReader : UVehicleAnimInstance {
  static const FVehicleAnimInstanceProxy* Read(UVehicleAnimInstance* Anim) {
    return GetProxyOnGameThreadStatic<FVehicleAnimInstanceProxy>(Anim);
  }
};
inline Array OriginalWheels(UCarlaEpisode& Episode,uint32 Id) {
  Array Rows;
  auto* Anim=WheelAnimation(Episode,Id,false);
  if (!Anim || !IsInGameThread()) return Rows;
  const auto* Proxy=FCompletedWheelReader::Read(Anim);
  if (!Proxy || Proxy->GetWheelAnimData().Num()!=4) return Rows;
  // These are the offsets the completed animation graph actually consumed.
  for (const FWheelAnimData& Wheel: Proxy->GetWheelAnimData()) {
    auto R=Object();
    R->SetStringField(TEXT("bone"),Wheel.BoneName.ToString());
    R->SetNumberField(TEXT("pitch"),Wheel.RotOffset.Pitch);
    R->SetNumberField(TEXT("yaw"),Wheel.RotOffset.Yaw);
    R->SetNumberField(TEXT("z_cm"),Wheel.LocOffset.Z);
    Rows.Add(MakeShared<FJsonValueObject>(R));
  }
  return Rows;
}
inline bool ApplyWheels(UCarlaEpisode& Episode,const std::string& Input,bool Locked,std::string& Output) {
  if (!FParse::Param(FCommandLine::Get(),TEXT("StrataM10ReplayWheels")) || Input.size()>4096) return false;
  Json J;
  if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(UTF8_TO_TCHAR(Input.c_str())),J) || !J.IsValid()) return false;
  FString Op,Presented;
  if (!J->TryGetStringField(TEXT("op"),Op) || Op!=TEXT("apply_measured_wheels")) return false;
  const auto Key=FPlatformMisc::GetEnvironmentVariable(TEXT("STRATADRIVE_M10_VISUAL_INSPECT_KEY"));
  auto R=Object();R->SetBoolField(TEXT("ok"),false);
  const TArray<TSharedPtr<FJsonValue>>* Rows=nullptr; double Id=0;
  if (!Locked && !FParse::Param(FCommandLine::Get(),TEXT("StrataM7NativeProbe")) &&
      !FParse::Param(FCommandLine::Get(),TEXT("nullrhi")) && Episode.GetSettings().bSynchronousMode &&
      Key.Len()==64 && J->TryGetStringField(TEXT("key"),Presented) && Presented==Key &&
      J->TryGetNumberField(TEXT("actor"),Id) && FMath::IsFinite(Id) && Id>=1 && Id<=MAX_uint32 && Id==uint32(Id) &&
      J->TryGetArrayField(TEXT("wheels"),Rows) && Rows->Num()==4) {
    auto* Anim=WheelAnimation(Episode,uint32(Id),true);
    if (Anim) {
      const auto* Movement=Anim->GetWheeledVehicleMovementComponent();
      float Pitch[4],Yaw[4],Height[4]; bool Valid=Movement && Movement->WheelSetups.Num()==4;
      for (int32 I=0;Valid && I<4;++I) {
        const TSharedPtr<FJsonObject>* Item=nullptr;FString Name;
        double P=0,Y=0,H=0;
        Valid=(*Rows)[I]->TryGetObject(Item) && (*Item)->TryGetStringField(TEXT("bone"),Name) &&
          Name==Movement->WheelSetups[I].BoneName.ToString() && (*Item)->TryGetNumberField(TEXT("pitch"),P) &&
          (*Item)->TryGetNumberField(TEXT("yaw"),Y) && (*Item)->TryGetNumberField(TEXT("z_cm"),H) &&
          FMath::IsFinite(P) && FMath::IsFinite(Y) && FMath::IsFinite(H) &&
          FMath::Abs(P)<=MAX_flt && FMath::Abs(Y)<=MAX_flt && FMath::Abs(H)<=MAX_flt;
        if (Valid) {Pitch[I]=float(P);Yaw[I]=float(Y);Height[I]=float(H);}
      }
      if (Valid) {
        for (uint8 I=0;I<4;++I) {
          Anim->SetWheelRotYaw(I,Yaw[I]);Anim->SetWheelPitchAngle(I,Pitch[I]);Anim->SetWheelHeight(I,Height[I]);
        }
        R->SetBoolField(TEXT("ok"),true);
      }
    }
  }
  FString Text;FJsonSerializer::Serialize(R.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));
  Output=TCHAR_TO_UTF8(*Text);return true;
}
}
PRAGMA_ENABLE_DEPRECATION_WARNINGS

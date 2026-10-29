#include "Carla.h"
#include "M7NoDriveMovement.h"
#include "M7SolverTrace.h"
#include "vehicle/PxVehicleNoDrive.h"
#include "PxVehicleSuspWheelTire4.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

// Other diagnostic profiles can still load an uninstrumented engine.
extern "C" bool M7SolverKeepProtectedSteerSleep(const void*) __attribute__((weak));
extern "C" void M7SolverStart(const void*) __attribute__((weak));
extern "C" const M7SolverTrace* M7SolverFinish(const void*) __attribute__((weak));

bool UM7NoDriveMovement::BeginSolverWork(bool KeepProtectedSteerSleep)
{
  if (!HasNoDrive() || DiagnosticSubsteps != 320 || !M7SolverStart || !M7SolverFinish) return false;
  M7SolverStart(PVehicle);
  return !KeepProtectedSteerSleep || (M7SolverKeepProtectedSteerSleep && M7SolverKeepProtectedSteerSleep(PVehicle));
}

namespace {
TArray<TSharedPtr<FJsonValue>> TraceSteps(const M7SolverTrace& Trace) {
  TArray<TSharedPtr<FJsonValue>> Rows;
  for (unsigned K=0; K<Trace.count && K<320; ++K) {
    const auto& Q = Trace.steps[K];
      auto Row = MakeShared<FJsonObject>();
      Row->SetNumberField(TEXT("ordinal"), Q.ordinal);
      Row->SetNumberField(TEXT("count"), Q.count);
      Row->SetNumberField(TEXT("block"), Q.block);
      Row->SetNumberField(TEXT("dt_s"), Q.dt);
      const float* Values[] = {Q.before,Q.after,Q.drive,Q.brake,Q.tire,Q.damping};
      const TCHAR* Names[] = {TEXT("before_rad_s"),TEXT("after_rad_s"),TEXT("drive_nm"),TEXT("brake_nm"),TEXT("tire_nm"),TEXT("damping_nm_s")};
      for (unsigned Field=0; Field<6; ++Field) {
        TArray<TSharedPtr<FJsonValue>> Array;
        for (unsigned W=0; W<4; ++W) {
          const double Value = Values[Field][W];
          if (FMath::IsFinite(Value)) Array.Add(MakeShared<FJsonValueNumber>(Value/(Field<2 ? 1.0 : 10000.0)));
          else Array.Add(MakeShared<FJsonValueString>(FString::Printf(TEXT("%g"), Value)));
        }
        Row->SetArrayField(Names[Field], Array);
      }
    Rows.Add(MakeShared<FJsonValueObject>(Row));
  }
  return Rows;
}
}
FString UM7NoDriveMovement::SolverTraceSteps(const M7SolverTrace& Trace) {
  auto R = MakeShared<FJsonObject>(); R->SetArrayField(TEXT("steps"), TraceSteps(Trace));
  FString Out; FJsonSerializer::Serialize(R, TJsonWriterFactory<>::Create(&Out)); return Out;
}

FString UM7NoDriveMovement::FinishSolverWork(bool& Valid, M7SolverTrace* Saved)
{
  Valid = false;
  auto R = MakeShared<FJsonObject>();
  R->SetStringField(TEXT("source"), TEXT("PhysX3.4.NoDrive.integrator.postOmega.v1"));
  R->SetStringField(TEXT("definition"), TEXT("sum(drive_torque_Nm * post_solver_omega_rad_s * solver_dt_s); signed discrete motor work"));
  auto* T = HasNoDrive() && M7SolverFinish ? M7SolverFinish(PVehicle) : nullptr;
  if (T) {
    R->SetNumberField(TEXT("abi"), T->abi);
    const bool HeldSteer = T->abi == 2 && T->protected_steer_hold == 1;
    R->SetBoolField(TEXT("protected_steer_hold"), HeldSteer);
    R->SetNumberField(TEXT("begins"), T->begins);
    R->SetNumberField(TEXT("ends"), T->ends);
    R->SetNumberField(TEXT("sleeping"), T->sleeping);
    R->SetNumberField(TEXT("wheels"), T->wheels);
    R->SetNumberField(TEXT("count"), T->count);
    R->SetNumberField(TEXT("overflow"), T->overflow);
    R->SetNumberField(TEXT("solver_dt_s"), T->dt);
    Valid = T->abi == 2 && T->protected_steer_hold <= 1 && T->begins == 1 && T->ends == 1 && T->wheels == 4 &&
      T->overflow == 0 && T->dt == (FParse::Param(FCommandLine::Get(), TEXT("StrataM7Wall5ms")) ? .005f : .01f) &&
      ((T->sleeping == 0 && T->count == 320) || (T->sleeping == 1 && T->count == 0));
    const auto* V = static_cast<const physx::PxVehicleNoDrive*>(PVehicle);
    double Work[4] = {};
    bool Forward = true;
    TArray<TSharedPtr<FJsonValue>> Means;
    for (unsigned K=0; K<T->count && K<320; ++K) {
      const auto& Q = T->steps[K];
      Valid = Valid && Q.ordinal == K && Q.count == 320 && Q.block == 0 && Q.dt == T->dt*(1.f/320.f);
      const float* Values[] = {Q.before,Q.after,Q.drive,Q.brake,Q.tire,Q.damping};
      for (unsigned Field=0; Field<6; ++Field)
        for (unsigned W=0; W<4; ++W) Valid = Valid && FMath::IsFinite(Values[Field][W]);
      for (unsigned W=0; W<4; ++W) {
        Valid = Valid && !PVehicle->mWheelsSimData.getIsWheelDisabled(W) && Q.drive[W] == V->getDriveTorque(W) &&
          (!K || Q.before[W] == T->steps[K-1].after[W]);
        Work[W] += double(Q.drive[W])/10000.0*double(Q.after[W])*double(Q.dt);
      }
      // V1 equal rear torque is conjugate to the rear mean shaft speed.
      const double Shaft = (double(Q.after[2])+double(Q.after[3]))/2;
      if (Q.drive[2] != Q.drive[3] || Q.drive[0] != 0 || Q.drive[1] != 0 ||
          ((Q.drive[2] != 0 || Q.drive[3] != 0) && (Shaft < 0 || Shaft > 100))) Forward = false;
      if (Saved) {
        if (FMath::IsFinite(Shaft)) Means.Add(MakeShared<FJsonValueNumber>(Shaft));
        else Means.Add(MakeShared<FJsonValueString>(TEXT("nonfinite")));
      }
    }
    TArray<TSharedPtr<FJsonValue>> WorkJson;
    for (unsigned W=0; W<4; ++W) {
      const auto* Block = PVehicle->mWheelsDynData.getWheel4DynData();
      Valid = Valid && FMath::IsFinite(Work[W]) && (T->sleeping ?
        (V->getDriveTorque(W) == 0 && (V->getSteerAngle(W) == 0 || HeldSteer) &&
         PVehicle->getRigidDynamicActor()->isSleeping() && Block[0].mWheelSpeeds[W] == 0) :
        (T->count == 320 && Block[0].mWheelSpeeds[W] == T->steps[319].after[W]));
      if (FMath::IsFinite(Work[W])) WorkJson.Add(MakeShared<FJsonValueNumber>(Work[W]));
      else WorkJson.Add(MakeShared<FJsonValueString>(FString::Printf(TEXT("%g"), Work[W])));
    }
    if (Saved) {
      if (Valid) *Saved = *T;
      R->SetArrayField(TEXT("rear_mean_rad_s"), Means);
      R->SetStringField(TEXT("trace_delivery"), TEXT("bounded_raw_journal; drain_before_close"));
    } else R->SetArrayField(TEXT("steps"), TraceSteps(*T));
    R->SetArrayField(TEXT("motor_work_j"), WorkJson);
    R->SetBoolField(TEXT("forward_energy_eligible"), Valid && Forward);
  }
  R->SetBoolField(TEXT("valid"), Valid);
  FString Out;
  FJsonSerializer::Serialize(R, TJsonWriterFactory<>::Create(&Out));
  return Out;
}

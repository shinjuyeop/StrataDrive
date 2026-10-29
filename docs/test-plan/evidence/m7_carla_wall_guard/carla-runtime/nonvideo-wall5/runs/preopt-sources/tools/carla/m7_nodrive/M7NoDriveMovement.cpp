#include "Carla.h"
#include "M7NoDriveMovement.h"
#include "Components/PrimitiveComponent.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysXPublic.h"
#include "vehicle/PxVehicleNoDrive.h"
#include "PxVehicleSuspWheelTire4.h"
#include "VehicleWheel.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

bool UM7NoDriveMovement::HasNoDrive() const
{
  return bZeroProbe && PVehicle && !PVehicleDrive &&
    PVehicle->getVehicleType() == physx::PxVehicleTypes::eNODRIVE &&
    PVehicle->mWheelsSimData.getNbWheels() == 4;
}

bool UM7NoDriveMovement::EnableZeroProbe(unsigned VehicleSubsteps)
{
  if (bZeroProbe || !PVehicle || WheelSetups.Num() != 4 ||
      (VehicleSubsteps != 0 && VehicleSubsteps != 20 && VehicleSubsteps != 40 && VehicleSubsteps != 80 &&
       VehicleSubsteps != 160 && VehicleSubsteps != 320 && VehicleSubsteps != 640)) return false;
  bZeroProbe = true;
  DiagnosticSubsteps = VehicleSubsteps;
  RecreatePhysicsState();
  ClearInputs();
  return HasNoDrive();
}

void UM7NoDriveMovement::ResetZeroProbe()
{
  if (!bZeroProbe) return;
  ClearInputs();
  RecreatePhysicsState();
  ClearInputs();
}

void UM7NoDriveMovement::SetupVehicleDrive(physx::PxVehicleWheelsSimData* Data)
{
  if (!bZeroProbe) { Super::SetupVehicleDrive(Data); return; }
  ++Generation;
  PVehicle = nullptr;
  PVehicleDrive = nullptr;
  if (!UpdatedPrimitive || Data->getNbWheels() != 4) { Data->free(); return; }
  auto* Vehicle = physx::PxVehicleNoDrive::allocate(4);
  // Separate diagnostic candidate only. World/ECU rates, tire law and effort are unchanged.
  if (DiagnosticSubsteps) Data->setSubStepCount(Data->getThresholdLongSpeed(), DiagnosticSubsteps, DiagnosticSubsteps);
  bool Ready = false;
  FPhysicsCommand::ExecuteWrite(UpdatedPrimitive->GetBodyInstance()->ActorHandle,
    [&](const FPhysicsActorHandle& Actor) {
      auto* Body = Actor.SyncActor ? Actor.SyncActor->is<physx::PxRigidDynamic>() : nullptr;
      if (Body) {
        Vehicle->setup(GPhysXSDK, Body, *Data);
        Vehicle->setToRestState();
        Ready = true;
      }
    });
  Data->free();
  if (Ready) PVehicle = Vehicle;
  else Vehicle->free();
}

bool UM7NoDriveMovement::NumericalProfileMatches() const
{
  return HasNoDrive() && (!DiagnosticSubsteps ||
    (PVehicle->mWheelsSimData.getLowForwardSpeedSubStepCount() == DiagnosticSubsteps &&
     PVehicle->mWheelsSimData.getHighForwardSpeedSubStepCount() == DiagnosticSubsteps));
}

void UM7NoDriveMovement::UpdateSimulation(float DeltaTime)
{
  // The bound ego never executes the stock engine/gear/control smoothing path.
  if (!bZeroProbe) Super::UpdateSimulation(DeltaTime);
}

void UM7NoDriveMovement::GenerateTireForces(UVehicleWheel* Wheel, const FTireShaderInput& Input, FTireShaderOutput& Output)
{
  Super::GenerateTireForces(Wheel, Input, Output);
  // Read-only callback witness. No alternate shader, tire law or output filtering.
  // Callbacks can be skipped by PhysX; ordinal is NOT a complete substep/work trace.
  if (bZeroProbe && DiagnosticSubsteps && TireObservations.Num() < 4096)
    TireObservations.Add({static_cast<unsigned>(Wheel->WheelIndex), Input.WheelOmega,
      Input.LongSlip, Input.TireLoad, Output.WheelTorque, Output.LongForce});
}

bool UM7NoDriveMovement::InputsAreZero() const
{
  if (!HasNoDrive()) return false;
  const auto* Vehicle = static_cast<const physx::PxVehicleNoDrive*>(PVehicle);
  for (unsigned W = 0; W != 4; ++W)
    if (Vehicle->getDriveTorque(W) != 0 || Vehicle->getBrakeTorque(W) != 0 ||
        Vehicle->getSteerAngle(W) != 0) return false;
  return true;
}

void UM7NoDriveMovement::ClearInputs()
{
  if (!HasNoDrive()) return;
  TireObservations.Reset();
  auto* Vehicle = static_cast<physx::PxVehicleNoDrive*>(PVehicle);
  for (unsigned W = 0; W != 4; ++W) {
    Vehicle->setDriveTorque(W, 0);
    Vehicle->setBrakeTorque(W, 0);
    Vehicle->setSteerAngle(W, 0);
  }
}

FString UM7NoDriveMovement::DescribePhysics() const
{
  auto Object = MakeShared<FJsonObject>();
  Object->SetBoolField(TEXT("nodrive"), HasNoDrive());
  Object->SetBoolField(TEXT("inputs_zero"), InputsAreZero());
  Object->SetStringField(TEXT("generation"), FString::Printf(TEXT("%llu"),
    static_cast<unsigned long long>(Generation)));
  TArray<TSharedPtr<FJsonValue>> Wheels;
  if (HasNoDrive()) {
    Object->SetStringField(TEXT("numerical_profile"), DiagnosticSubsteps ?
      FString::Printf(TEXT("vehicle%u-diagnostic-v1"), DiagnosticSubsteps) : TEXT("asset-default"));
    Object->SetNumberField(TEXT("vehicle_substeps_low"), PVehicle->mWheelsSimData.getLowForwardSpeedSubStepCount());
    Object->SetNumberField(TEXT("vehicle_substeps_high"), PVehicle->mWheelsSimData.getHighForwardSpeedSubStepCount());
    Object->SetNumberField(TEXT("vehicle_substeps_threshold_m_s"), PVehicle->mWheelsSimData.getThresholdLongSpeed() / 100.0);
    Object->SetNumberField(TEXT("sdk_tolerance_length_cm"), GPhysXSDK->getTolerancesScale().length);
    const auto* NoDrive = static_cast<const physx::PxVehicleNoDrive*>(PVehicle);
    for (unsigned W = 0; W != 4; ++W) {
      auto Wheel = MakeShared<FJsonObject>();
      const auto& Data = PVehicle->mWheelsSimData.getWheelData(W);
      const auto Offset = PVehicle->mWheelsSimData.getWheelCentreOffset(W);
      Wheel->SetNumberField(TEXT("index"), W);
      Wheel->SetStringField(TEXT("bone"), WheelSetups[W].BoneName.ToString());
      Wheel->SetNumberField(TEXT("radius_m"), Data.mRadius / 100.0);
      Wheel->SetNumberField(TEXT("inertia_kg_m2"), Data.mMOI / 10000.0);
      Wheel->SetNumberField(TEXT("damping_nm_s"), Data.mDampingRate / 10000.0);
      Wheel->SetNumberField(TEXT("longitudinal_stiffness_per_gravity"), PVehicle->mWheelsSimData.getTireData(W).mLongitudinalStiffnessPerUnitGravity);
      Wheel->SetNumberField(TEXT("max_brake_nm"), Data.mMaxBrakeTorque / 10000.0);
      Wheel->SetNumberField(TEXT("max_steer_rad"), Data.mMaxSteer);
      Wheel->SetNumberField(TEXT("offset_x_m"), Offset.x / 100.0);
      Wheel->SetNumberField(TEXT("offset_y_right_m"), Offset.y / 100.0);
      Wheel->SetNumberField(TEXT("set_drive_nm"), NoDrive->getDriveTorque(W) / 10000.0);
      Wheel->SetNumberField(TEXT("set_friction_nm"), NoDrive->getBrakeTorque(W) / 10000.0);
      Wheel->SetNumberField(TEXT("set_steer_right_rad"), NoDrive->getSteerAngle(W));
      // Preserve the old public API observation. In this fork it returns the
      // low-speed rendering correction, NOT always the integration state.
      Wheel->SetNumberField(TEXT("omega_rad_s"), PVehicle->mWheelsDynData.getWheelRotationSpeed(W));
      // Read-only serialization accessor, compiled against the pinned engine
      // header. No layout cast, engine mutation or v/r reconstruction.
      const auto* Dynamics = PVehicle->mWheelsDynData.getWheel4DynData();
      Wheel->SetNumberField(TEXT("solver_omega_rad_s"), Dynamics[W / 4].mWheelSpeeds[W % 4]);
      Wheel->SetStringField(TEXT("solver_omega_source"), TEXT("PhysX3.4.mWheelSpeeds.direct.v1"));
      Wheels.Add(MakeShared<FJsonValueObject>(Wheel));
    }
    Object->SetBoolField(TEXT("sleeping"), PVehicle->getRigidDynamicActor()->isSleeping());
    const auto* Body = PVehicle->getRigidDynamicActor();
    const auto Pose = Body->getGlobalPose();
    auto Vector = [](const physx::PxVec3& V, double Scale) {
      return TArray<TSharedPtr<FJsonValue>>{MakeShared<FJsonValueNumber>(V.x * Scale),
        MakeShared<FJsonValueNumber>(V.y * Scale), MakeShared<FJsonValueNumber>(V.z * Scale)};
    };
    Object->SetArrayField(TEXT("body_world_position_m"), Vector(Pose.p, .01));
    Object->SetArrayField(TEXT("com_velocity_world_m_s"), Vector(Body->getLinearVelocity(), .01));
    Object->SetArrayField(TEXT("angular_velocity_world_rad_s"), Vector(Body->getAngularVelocity(), 1));
    Object->SetNumberField(TEXT("body_forward_velocity_m_s"), Pose.q.getBasisVector0().dot(Body->getLinearVelocity()) / 100.0);
    Object->SetArrayField(TEXT("body_quaternion_xyzw"), {MakeShared<FJsonValueNumber>(Pose.q.x),
      MakeShared<FJsonValueNumber>(Pose.q.y), MakeShared<FJsonValueNumber>(Pose.q.z), MakeShared<FJsonValueNumber>(Pose.q.w)});
    // Save detailed callbacks only at low-speed nonzero effort, including every failing launch.
    // Wall feedback needs the original state promptly. The separate immutable
    // solver journal already retains every wheel force/omega/substep. These
    // legacy low-speed callback JSON objects duplicate that diagnostic evidence
    // and are deliberately excluded from the deadline-sensitive wall snapshot.
    if (!FParse::Param(FCommandLine::Get(), TEXT("StrataM7WallNative")) &&
        DiagnosticSubsteps && Body->getLinearVelocity().magnitude() < 25.0f &&
        (NoDrive->getDriveTorque(2) != 0 || NoDrive->getDriveTorque(3) != 0)) {
      TArray<TSharedPtr<FJsonValue>> Trace;
      for (const auto& T : TireObservations) {
        auto Row = MakeShared<FJsonObject>();
        Row->SetNumberField(TEXT("wheel"), T.Wheel);
        Row->SetNumberField(TEXT("omega_before_rad_s"), T.Omega);
        Row->SetNumberField(TEXT("long_slip"), T.Slip);
        Row->SetNumberField(TEXT("tire_load_n"), T.Load / 100.0);
        Row->SetNumberField(TEXT("tire_torque_nm"), T.Torque / 10000.0);
        Row->SetNumberField(TEXT("long_force_n"), T.LongForce / 100.0);
        Trace.Add(MakeShared<FJsonValueObject>(Row));
      }
      Object->SetArrayField(TEXT("tire_callbacks"), Trace);
      Object->SetStringField(TEXT("tire_callback_scope"), TEXT("ordered calls only; skipped calls possible; NOT solver work coverage"));
    }
  }
  Object->SetArrayField(TEXT("wheels"), Wheels);
  FString Result;
  FJsonSerializer::Serialize(Object, TJsonWriterFactory<>::Create(&Result));
  return Result;
}

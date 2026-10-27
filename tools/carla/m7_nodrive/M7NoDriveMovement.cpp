#include "Carla.h"
#include "M7NoDriveMovement.h"
#include "Components/PrimitiveComponent.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysXPublic.h"
#include "vehicle/PxVehicleNoDrive.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

bool UM7NoDriveMovement::HasNoDrive() const
{
  return bZeroProbe && PVehicle && !PVehicleDrive &&
    PVehicle->getVehicleType() == physx::PxVehicleTypes::eNODRIVE &&
    PVehicle->mWheelsSimData.getNbWheels() == 4;
}

bool UM7NoDriveMovement::EnableZeroProbe(bool VehicleTwenty)
{
  if (bZeroProbe || !PVehicle || WheelSetups.Num() != 4) return false;
  bZeroProbe = true;
  bVehicleTwenty = VehicleTwenty;
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
  if (bVehicleTwenty) Data->setSubStepCount(Data->getThresholdLongSpeed(), 20, 20);
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
  return HasNoDrive() && (!bVehicleTwenty ||
    (PVehicle->mWheelsSimData.getLowForwardSpeedSubStepCount() == 20 &&
     PVehicle->mWheelsSimData.getHighForwardSpeedSubStepCount() == 20));
}

void UM7NoDriveMovement::UpdateSimulation(float DeltaTime)
{
  // The bound ego never executes the stock engine/gear/control smoothing path.
  if (!bZeroProbe) Super::UpdateSimulation(DeltaTime);
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
    Object->SetStringField(TEXT("numerical_profile"), bVehicleTwenty ? TEXT("vehicle20-diagnostic-v1") : TEXT("asset-default"));
    Object->SetNumberField(TEXT("vehicle_substeps_low"), PVehicle->mWheelsSimData.getLowForwardSpeedSubStepCount());
    Object->SetNumberField(TEXT("vehicle_substeps_high"), PVehicle->mWheelsSimData.getHighForwardSpeedSubStepCount());
    Object->SetNumberField(TEXT("vehicle_substeps_threshold_m_s"), PVehicle->mWheelsSimData.getThresholdLongSpeed() / 100.0);
    const auto* NoDrive = static_cast<const physx::PxVehicleNoDrive*>(PVehicle);
    for (unsigned W = 0; W != 4; ++W) {
      auto Wheel = MakeShared<FJsonObject>();
      const auto& Data = PVehicle->mWheelsSimData.getWheelData(W);
      const auto Offset = PVehicle->mWheelsSimData.getWheelCentreOffset(W);
      Wheel->SetNumberField(TEXT("index"), W);
      Wheel->SetStringField(TEXT("bone"), WheelSetups[W].BoneName.ToString());
      Wheel->SetNumberField(TEXT("radius_m"), Data.mRadius / 100.0);
      Wheel->SetNumberField(TEXT("max_brake_nm"), Data.mMaxBrakeTorque / 10000.0);
      Wheel->SetNumberField(TEXT("max_steer_rad"), Data.mMaxSteer);
      Wheel->SetNumberField(TEXT("offset_x_m"), Offset.x / 100.0);
      Wheel->SetNumberField(TEXT("offset_y_right_m"), Offset.y / 100.0);
      Wheel->SetNumberField(TEXT("set_drive_nm"), NoDrive->getDriveTorque(W) / 10000.0);
      Wheel->SetNumberField(TEXT("set_friction_nm"), NoDrive->getBrakeTorque(W) / 10000.0);
      Wheel->SetNumberField(TEXT("set_steer_right_rad"), NoDrive->getSteerAngle(W));
      // Raw signed solver value: no epsilon, absolute value or stationary clamp.
      Wheel->SetNumberField(TEXT("omega_rad_s"), PVehicle->mWheelsDynData.getWheelRotationSpeed(W));
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
  }
  Object->SetArrayField(TEXT("wheels"), Wheels);
  FString Result;
  FJsonSerializer::Serialize(Object, TJsonWriterFactory<>::Create(&Result));
  return Result;
}

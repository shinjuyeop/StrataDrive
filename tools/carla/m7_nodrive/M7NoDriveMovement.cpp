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

bool UM7NoDriveMovement::EnableZeroProbe()
{
  if (bZeroProbe || !PVehicle || WheelSetups.Num() != 4) return false;
  bZeroProbe = true;
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
  }
  Object->SetArrayField(TEXT("wheels"), Wheels);
  FString Result;
  FJsonSerializer::Serialize(Object, TJsonWriterFactory<>::Create(&Result));
  return Result;
}

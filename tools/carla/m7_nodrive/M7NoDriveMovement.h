// StrataDrive experimental CARLA extension. Not a normal-driving backend.
#pragma once

#include "WheeledVehicleMovementComponent4W.h"
#include "M7NoDriveMovement.generated.h"

struct FM7WheelEffort {
  double Drive[4] = {}, Brake[4] = {}, Steer[4] = {};
};

UCLASS()
class CARLA_API UM7NoDriveMovement : public UWheeledVehicleMovementComponent4W
{
  GENERATED_BODY()
public:
  bool EnableZeroProbe();
  bool IsZeroProbe() const { return bZeroProbe; }
  bool HasNoDrive() const;
  bool InputsAreZero() const;
  uint64 PhysicsGeneration() const { return Generation; }
  void ClearInputs();
  void ResetZeroProbe();
  FString DescribePhysics() const;
  FString DescribeGeometry();
  bool ValidateV1() const;
  bool PrepareV1(double Angle, double Torque, double Pressure, FM7WheelEffort& Out) const;
  bool ApplyEffort(const FM7WheelEffort& Effort);
  bool EffortMatches(const FM7WheelEffort& Effort) const;
protected:
  virtual void SetupVehicleDrive(physx::PxVehicleWheelsSimData* Data) override;
  virtual void UpdateSimulation(float DeltaTime) override;
private:
  bool bZeroProbe = false;
  uint64 Generation = 0;
};

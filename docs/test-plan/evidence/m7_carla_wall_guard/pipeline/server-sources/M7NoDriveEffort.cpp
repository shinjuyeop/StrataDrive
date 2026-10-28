// Explicit virtual EV law, not OEM calibration. No delay/filter/motion/energy integration.
#include "Carla.h"
#include "M7NoDriveMovement.h"
#include "M7NoDriveModelConstants.h"
#include "PhysXPublic.h"
#include "vehicle/PxVehicleNoDrive.h"
#include <cmath>

bool UM7NoDriveMovement::ValidateV1() const
{
  if (!HasNoDrive() || PVehicle->getRigidDynamicActor()->getMass() != M7V1::Mass) return false;
  for (unsigned W = 0; W != 4; ++W) {
    const auto& D = PVehicle->mWheelsSimData.getWheelData(W);
    const auto P = PVehicle->mWheelsSimData.getWheelCentreOffset(W);
    // Exact measured binary geometry. A changed asset needs a separately reviewed model.
    if (WheelSetups[W].BoneName.ToString() != UTF8_TO_TCHAR(M7V1::Bones[W]) ||
        D.mRadius / 100.0 != M7V1::Radius[W] ||
        D.mMaxBrakeTorque / 10000.0 != M7V1::MaxBrake[W] ||
        D.mMaxSteer != M7V1::MaxSteer[W] ||
        P.x / 100.0 != M7V1::X[W] || P.y / 100.0 != M7V1::Y[W]) return false;
  }
  return true;
}

bool UM7NoDriveMovement::PrepareV1(double Angle, double Torque, double Pressure, FM7WheelEffort& Out) const
{
  if (!ValidateV1() || !std::isfinite(Angle) || !std::isfinite(Torque) || !std::isfinite(Pressure) ||
      Angle < M7V1::SteeringRange[0] || Angle > M7V1::SteeringRange[1] ||
      Torque < M7V1::DriveRange[0] || Torque > M7V1::DriveRange[1] ||
      Pressure < M7V1::PressureRange[0] || Pressure > M7V1::PressureRange[1]) return false;
  FM7WheelEffort E;
  const double L = M7V1::X[0] - M7V1::X[2];
  const double HalfTrack = (M7V1::Y[1] - M7V1::Y[0]) / 2;
  const double T = std::tan(Angle);
  E.Steer[0] = -std::atan2(L * T, L - HalfTrack * T);
  E.Steer[1] = -std::atan2(L * T, L + HalfTrack * T);
  for (unsigned W = 0; W != 4; ++W) {
    E.Drive[W] = Torque * M7V1::MotorFractions[W];
    E.Brake[W] = Pressure * M7V1::BrakeGain * M7V1::BrakeFractions[W];
    if (!std::isfinite(E.Steer[W]) || std::abs(E.Steer[W]) > M7V1::MaxSteer[W] ||
        !std::isfinite(E.Brake[W]) || E.Brake[W] < 0 || E.Brake[W] > M7V1::MaxBrake[W]) return false;
  }
  Out = E;
  return true;
}

bool UM7NoDriveMovement::EffortMatches(const FM7WheelEffort& E) const
{
  if (!HasNoDrive()) return false;
  const auto* V = static_cast<const physx::PxVehicleNoDrive*>(PVehicle);
  for (unsigned W = 0; W != 4; ++W)
    if (V->getDriveTorque(W) != static_cast<float>(E.Drive[W] * 10000.0) ||
        V->getBrakeTorque(W) != static_cast<float>(E.Brake[W] * 10000.0) ||
        V->getSteerAngle(W) != static_cast<float>(E.Steer[W])) return false;
  return true;
}

bool UM7NoDriveMovement::ApplyEffort(const FM7WheelEffort& E)
{
  if (!InputsAreZero()) return false;
  auto* V = static_cast<physx::PxVehicleNoDrive*>(PVehicle);
  // Only the guarded pre-physics owner calls this; all twelve setters written each frame.
  for (unsigned W = 0; W != 4; ++W) {
    V->setDriveTorque(W, static_cast<float>(E.Drive[W] * 10000.0));
    V->setBrakeTorque(W, static_cast<float>(E.Brake[W] * 10000.0));
    V->setSteerAngle(W, static_cast<float>(E.Steer[W]));
  }
  if (EffortMatches(E)) return true;
  ClearInputs();
  return false;
}

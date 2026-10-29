// Read-only rest geometry. No control setters, state recreation or world tick.
#include "Carla.h"
#include "M7NoDriveMovement.h"
#include "Components/SkinnedMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/SkeletalMesh.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/BodySetup.h"
#include "VehicleWheel.h"
#include "PhysXPublic.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

namespace M7Geometry {
using Json = TSharedPtr<FJsonObject>;
TArray<TSharedPtr<FJsonValue>> Vector(const FVector& V, double Scale = .01)
{
  return {MakeShared<FJsonValueNumber>(V.X * Scale),
          MakeShared<FJsonValueNumber>(V.Y * Scale),
          MakeShared<FJsonValueNumber>(V.Z * Scale)};
}
FVector FromPx(const physx::PxVec3& V) { return FVector(V.x, V.y, V.z); }
FTransform FromPx(const physx::PxTransform& P)
{
  return FTransform(FQuat(P.q.x, P.q.y, P.q.z, P.q.w), FromPx(P.p));
}
Json Transform(const FTransform& T)
{
  auto J = MakeShared<FJsonObject>();
  const auto Q = T.GetRotation();
  J->SetArrayField(TEXT("translation_m"), Vector(T.GetTranslation()));
  J->SetArrayField(TEXT("quaternion_xyzw"), {MakeShared<FJsonValueNumber>(Q.X),
    MakeShared<FJsonValueNumber>(Q.Y), MakeShared<FJsonValueNumber>(Q.Z), MakeShared<FJsonValueNumber>(Q.W)});
  J->SetArrayField(TEXT("scale"), Vector(T.GetScale3D(), 1));
  return J;
}
}

FString UM7NoDriveMovement::DescribeGeometry()
{
  using namespace M7Geometry;
  auto J = MakeShared<FJsonObject>();
  auto* Mesh = GetMesh();
  const bool Valid = HasNoDrive() && GetOwner() && Mesh && Mesh->SkeletalMesh &&
    Mesh->GetBodyInstance() && Mesh->GetBodyInstance()->BodySetup.IsValid();
  J->SetStringField(TEXT("schema"), TEXT("m7-rest-geometry-v1"));
  J->SetBoolField(TEXT("valid"), Valid);
  J->SetStringField(TEXT("basis"), TEXT("UE x-forward y-right z-up; SI m/kg/rad"));
  J->SetStringField(TEXT("kind"), TEXT("reference/rest geometry; NOT contact patch or calibration"));
  J->SetStringField(TEXT("generation"), FString::Printf(TEXT("%llu"),
    static_cast<unsigned long long>(PhysicsGeneration())));
  if (Valid) {
    const auto* Body = PVehicle->getRigidDynamicActor();
    const auto BodyWorld = Body->getGlobalPose();
    const auto ComBody = Body->getCMassLocalPose();
    const auto ActorWorld = GetOwner()->GetActorTransform();
    const auto RootBone = Mesh->GetBodyInstance()->BodySetup->BoneName;
    J->SetStringField(TEXT("root_body_bone"), RootBone.ToString());
    J->SetObjectField(TEXT("actor_world"), Transform(ActorWorld));
    J->SetObjectField(TEXT("mesh_world"), Transform(Mesh->GetComponentTransform()));
    J->SetObjectField(TEXT("body_world"), Transform(FromPx(BodyWorld)));
    J->SetObjectField(TEXT("com_body"), Transform(FromPx(ComBody)));
    J->SetObjectField(TEXT("reference_root_body_mesh"), Transform(
      FTransform(Mesh->SkeletalMesh->GetComposedRefPoseMatrix(RootBone))));
    J->SetArrayField(TEXT("mesh_relative_scale"), Vector(Mesh->GetRelativeScale3D(), 1));
    J->SetArrayField(TEXT("com_nudge_m"), Vector(UpdatedPrimitive->BodyInstance.COMNudge));
    J->SetNumberField(TEXT("mass_kg"), Body->getMass());
    J->SetArrayField(TEXT("inertia_kg_m2"), Vector(FromPx(Body->getMassSpaceInertiaTensor()), .0001));
    J->SetBoolField(TEXT("inputs_zero"), InputsAreZero());
    TArray<TSharedPtr<FJsonValue>> Wheels;
    for (unsigned W = 0; W != 4; ++W) {
      auto V = MakeShared<FJsonObject>();
      const auto& Setup = WheelSetups[W];
      const auto* Wheel = Setup.WheelClass.GetDefaultObject();
      const auto Com = PVehicle->mWheelsSimData.getWheelCentreOffset(W);
      const auto LocalBody = ComBody.transform(Com);
      const auto World = BodyWorld.transform(LocalBody);
      V->SetNumberField(TEXT("index"), W);
      V->SetStringField(TEXT("bone"), Setup.BoneName.ToString());
      V->SetArrayField(TEXT("reference_bone_mesh_m"), Vector(
        Mesh->SkeletalMesh->GetComposedRefPoseMatrix(Setup.BoneName).GetOrigin()));
      V->SetArrayField(TEXT("class_offset_m"), Vector(Wheel->Offset));
      V->SetArrayField(TEXT("setup_offset_m"), Vector(Setup.AdditionalOffset));
      V->SetArrayField(TEXT("ue_rest_body_m"), Vector(GetWheelRestingPosition(Setup)));
      V->SetArrayField(TEXT("px_rest_com_m"), Vector(FromPx(Com)));
      V->SetArrayField(TEXT("px_rest_body_m"), Vector(FromPx(LocalBody)));
      V->SetArrayField(TEXT("px_rest_world_m"), Vector(FromPx(World)));
      V->SetArrayField(TEXT("px_rest_actor_m"), Vector(
        ActorWorld.InverseTransformPosition(FromPx(World))));
      const auto& Data = PVehicle->mWheelsSimData.getWheelData(W);
      V->SetNumberField(TEXT("radius_m"), Data.mRadius / 100.0);
      V->SetNumberField(TEXT("max_steer_rad"), Data.mMaxSteer);
      V->SetNumberField(TEXT("max_brake_nm"), Data.mMaxBrakeTorque / 10000.0);
      Wheels.Add(MakeShared<FJsonValueObject>(V));
    }
    J->SetArrayField(TEXT("wheels"), Wheels);
  }
  FString Result;
  FJsonSerializer::Serialize(J, TJsonWriterFactory<>::Create(&Result));
  return Result;
}

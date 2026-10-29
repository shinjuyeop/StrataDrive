#pragma once
#include "PxPhysicsAPI.h"
#include "SnippetVehicleCreate.h"
#include "SnippetVehicleFilterShader.h"
#include "SnippetVehicleSceneQuery.h"
#include "SnippetVehicleTireFriction.h"
#include "wheel_effort.hpp"
#include <array>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

namespace stratadrive::m7_nodrive {
// Upstream snippet geometry/material/suspension fixture, SI units. It is NOT
// the mkz_2020 asset, a calibrated StrataDrive vehicle, or CARLA's UE integration.
class Scene {
public:
    struct Errors final : physx::PxErrorCallback {
        std::vector<std::string> messages;
        void reportError(physx::PxErrorCode::Enum,const char* message,const char*,int) override {
            messages.emplace_back(message);
        }
    } errors;
    Scene() {
      try {
        using namespace physx;using namespace snippetvehicle;
        foundation_=PxCreateFoundation(PX_FOUNDATION_VERSION,allocator_,errors);
        if(!foundation_)throw std::runtime_error("foundation: "+diagnostic());
        physics_=PxCreatePhysics(PX_PHYSICS_VERSION,*foundation_,PxTolerancesScale(),true);
        if(!physics_)throw std::runtime_error("physics: "+diagnostic());
        extensions_initialized_=PxInitExtensions(*physics_,nullptr);
        if(!extensions_initialized_)throw std::runtime_error("extensions: "+diagnostic());
        PxSceneDesc desc(physics_->getTolerancesScale());desc.gravity=PxVec3(0,-9.81f,0);
        dispatcher_=PxDefaultCpuDispatcherCreate(1);desc.cpuDispatcher=dispatcher_;desc.filterShader=VehicleFilterShader;
        scene_=physics_->createScene(desc);material_=physics_->createMaterial(.5f,.5f,.6f);
        cooking_=PxCreateCooking(PX_PHYSICS_VERSION,*foundation_,PxCookingParams(PxTolerancesScale()));
        if(!scene_ || !material_ || !cooking_)throw std::runtime_error("scene resources: "+diagnostic());
        vehicle_initialized_=PxInitVehicleSDK(*physics_);
        if(!vehicle_initialized_)throw std::runtime_error("vehicle SDK: "+diagnostic());
        PxVehicleSetBasisVectors(PxVec3(0,1,0),PxVec3(0,0,1));
        PxVehicleSetUpdateMode(PxVehicleUpdateMode::eVELOCITY_CHANGE);
        query_=VehicleSceneQueryData::allocate(1,PX_MAX_NB_WHEELS,1,1,WheelSceneQueryPreFilterBlocking,nullptr,allocator_);
        batch_=VehicleSceneQueryData::setUpBatchedSceneQuery(0,*query_,scene_);
        friction_=createFrictionPairs(material_);
        ground_=createDrivablePlane(PxFilterData(COLLISION_FLAG_GROUND,COLLISION_FLAG_GROUND_AGAINST,0,0),material_,physics_);
        scene_->addActor(*ground_);
        VehicleDesc vd;
        vd.chassisMass=1500;vd.chassisDims=PxVec3(2.5f,2,5);
        const auto& d=vd.chassisDims;
        vd.chassisMOI=PxVec3((d.y*d.y+d.z*d.z)*vd.chassisMass/12,
            (d.x*d.x+d.z*d.z)*.8f*vd.chassisMass/12,(d.x*d.x+d.y*d.y)*vd.chassisMass/12);
        vd.chassisCMOffset=PxVec3(0,-d.y*.5f+.65f,.25f);vd.chassisMaterial=material_;
        vd.chassisSimFilterData=PxFilterData(COLLISION_FLAG_CHASSIS,COLLISION_FLAG_CHASSIS_AGAINST,0,0);
        vd.wheelMass=20;vd.wheelRadius=.5f;vd.wheelWidth=.4f;vd.wheelMOI=.5f*vd.wheelMass*vd.wheelRadius*vd.wheelRadius;
        vd.numWheels=4;vd.wheelMaterial=material_;
        vd.wheelSimFilterData=PxFilterData(COLLISION_FLAG_WHEEL,COLLISION_FLAG_WHEEL_AGAINST,0,0);
        vehicle_=createVehicleNoDrive(vd,physics_,cooking_);
        if(!vehicle_)throw std::runtime_error("NoDrive vehicle");
        vehicle_->getRigidDynamicActor()->setGlobalPose(PxTransform(PxVec3(0,d.y*.5f+vd.wheelRadius+1,0)));
        scene_->addActor(*vehicle_->getRigidDynamicActor());vehicle_->setToRestState();
        // Explicit solver-resolution experiment only. No tire/actuator/sensor
        // constants change. Absent env keeps upstream defaults (3 low / 1 high).
        if(const char* value=std::getenv("M7_NODRIVE_SUBSTEPS")) {
            char* end=nullptr;const auto count=std::strtoul(value,&end,10);
            if(!end || *end || count<1 || count>100)throw std::invalid_argument("substep probe count");
            vehicle_->mWheelsSimData.setSubStepCount(vehicle_->mWheelsSimData.getThresholdLongSpeed(),
                static_cast<physx::PxU32>(count),static_cast<physx::PxU32>(count));
        }
        // NoDrive helper orders rear wheels first. Verify geometry, do not assume
        // CARLA's FL/FR/RL/RR enum equals this SDK fixture's array indices.
        const auto& wheels=vehicle_->mWheelsSimData;
        if(!(wheels.getWheelCentreOffset(0).z<wheels.getWheelCentreOffset(2).z &&
             wheels.getWheelCentreOffset(0).x<wheels.getWheelCentreOffset(1).x &&
             wheels.getWheelCentreOffset(2).x<wheels.getWheelCentreOffset(3).x))
            throw std::runtime_error("unexpected snippet wheel geometry");
      } catch(...) {close();throw;}
    }
    ~Scene() {close();}
    Scene(const Scene&)=delete;Scene& operator=(const Scene&)=delete;
    physx::PxVehicleNoDrive& vehicle() {return *vehicle_;}
    static constexpr std::array<unsigned,4> order{2,3,0,1}; // project -> snippet
    m7_effort::Definition definition() const {
        const auto& w=vehicle_->mWheelsSimData;
        // Actual geometry readback for this fixture. Pressure table is deliberately
        // synthetic test data, not a real brake calibration or default for CARLA.
        return {w.getWheelCentreOffset(2).z-w.getWheelCentreOffset(0).z,
                w.getWheelCentreOffset(3).x-w.getWheelCentreOffset(2).x,
                {1.2,1.2,0,0},{0,0,150,150},{1500,1500,1500,1500},
                {{0,{0,0,0,0}},{100000,{1000,1000,1000,1000}},{150000,{1500,1500,1500,1500}}}};
    }
    bool step() {
        using namespace physx;
        PxVehicleWheels* vehicles[]{vehicle_};
        PxVehicleSuspensionRaycasts(batch_,1,vehicles,query_->getQueryResultBufferSize(),query_->getRaycastQueryResultBuffer(0));
        PxVehicleWheelQueryResult query_result{wheel_query_.data(),4};
        PxVehicleUpdates(.01f,scene_->getGravity(),*friction_,1,vehicles,&query_result);
        scene_->simulate(.01f);const bool fetched=scene_->fetchResults(true);++ticks;
        return fetched && errors.messages.empty();
    }
    std::array<bool,4> in_air() const {
        return {wheel_query_[order[0]].isInAir,wheel_query_[order[1]].isInAir,
                wheel_query_[order[2]].isInAir,wheel_query_[order[3]].isInAir};
    }
    unsigned ticks=0;
private:
    std::string diagnostic() const {return errors.messages.empty()?"no SDK diagnostic":errors.messages.back();}
    void close() {
        if(vehicle_) {vehicle_->getRigidDynamicActor()->release();vehicle_->free();}
        if(ground_)ground_->release();
        if(batch_)batch_->release();
        if(query_)query_->free(allocator_);
        if(friction_)friction_->release();
        if(vehicle_initialized_)physx::PxCloseVehicleSDK();
        if(material_)material_->release();
        if(cooking_)cooking_->release();
        if(scene_)scene_->release();
        if(dispatcher_)dispatcher_->release();
        if(extensions_initialized_)PxCloseExtensions();
        if(physics_)physics_->release();
        if(foundation_)foundation_->release();
    }
    bool extensions_initialized_=false,vehicle_initialized_=false;
    physx::PxDefaultAllocator allocator_;
    physx::PxFoundation* foundation_=nullptr;
    physx::PxPhysics* physics_=nullptr;
    physx::PxDefaultCpuDispatcher* dispatcher_=nullptr;
    physx::PxScene* scene_=nullptr;
    physx::PxMaterial* material_=nullptr;
    physx::PxCooking* cooking_=nullptr;
    snippetvehicle::VehicleSceneQueryData* query_=nullptr;
    physx::PxBatchQuery* batch_=nullptr;
    physx::PxVehicleDrivableSurfaceToTireFrictionPairs* friction_=nullptr;
    physx::PxRigidStatic* ground_=nullptr;
    physx::PxVehicleNoDrive* vehicle_=nullptr;
    std::array<physx::PxWheelQueryResult,4> wheel_query_{};
};
} // namespace stratadrive::m7_nodrive

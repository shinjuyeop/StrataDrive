#pragma once
// Standalone SDK prototype, not a CARLA/UE plugin or a network authority.
#include "actual_boundary.hpp"
#include "wheel_effort.hpp"
#include "vehicle/PxVehicleNoDrive.h"
#include "PxRigidDynamic.h"
#include <functional>
#include <mutex>
#include <set>
#include <stdexcept>

namespace stratadrive::m7_nodrive {
using namespace m7_test;
struct Observation {
    ActualBundle actual; // validated original CAN/provenance, never setter feedback
    Interval interval;
    m7_effort::Effort applied; // float-representable effort, NOT a new actuator Actual
    std::array<double,4> omega; // FL,FR,RL,RR; original signed SDK values
    bool sleeping;
    bool interval_work_valid=false; // no solver work instrumentation in this probe
};

class Port final : public Backend {
public:
    using Step = std::function<bool()>;
    Port(physx::PxVehicleNoDrive& vehicle,m7_effort::Definition definition,
         std::array<unsigned,4> project_to_native,Step step):
        vehicle_(vehicle),mapping_(std::move(definition)),order_(project_to_native),step_(std::move(step)) {
        const std::set<unsigned> indices(order_.begin(),order_.end());
        if(vehicle_.mWheelsSimData.getNbWheels()!=4 || indices!=std::set<unsigned>{0,1,2,3} || !step_)
            throw std::invalid_argument("NoDrive binding");
        std::lock_guard<std::mutex> lock(registry_mutex_);
        if(!registry_.insert(&vehicle_).second)throw std::invalid_argument("NoDrive already owned");
        // Do not silently overwrite an existing writer at construction.
        if(!clear_readback()) {
            registry_.erase(&vehicle_);
            throw std::invalid_argument("NoDrive has existing effort");
        }
    }
    ~Port() override {
        clear();std::lock_guard<std::mutex> lock(registry_mutex_);registry_.erase(&vehicle_);
    }
    Port(const Port&)=delete;
    Port& operator=(const Port&)=delete;
    const std::optional<Observation>& observation() const {return observed_;}
    const std::string& error() const {return error_;}
    unsigned completed_ticks() const {return completed_;}
    // Trusted lifecycle entry only. Resume requires a new boundary/port INIT.
    void pause() {error_="paused; new INIT required";pending_.reset();clear();observed_.reset();}
private:
    struct Pending {ActualBundle actual;Interval interval;m7_effort::Effort effort;};
    ApplyResult apply(const ActualBundle& a,const Interval& i) override {
        if(!error_.empty() || pending_ || i.end<=i.begin || i.end-i.begin!=10*ms ||
           (last_end_ && i.begin!=last_end_) || !a.steering.angle_rad || !a.drive.torque_nm || !a.brake.pressure_pa)
            return ApplyResult::Rejected;
        auto mapped=mapping_.map(*a.steering.angle_rad,*a.drive.torque_nm,*a.brake.pressure_pa);
        if(!mapped.effort)return ApplyResult::Rejected;
        // Convert all four wheels before any SDK mutation. SI SDK fixture only.
        // A UE adapter must apply its validated cm^2 scale at its own boundary.
        for(auto* values:{&mapped.effort->steer_right_rad,&mapped.effort->motor_nm,&mapped.effort->friction_nm})
            for(double& v:*values) {
                const float native=static_cast<float>(v);
                if(!std::isfinite(native))return ApplyResult::Rejected;
                v=native;
            }
        pending_=Pending{a,i,*mapped.effort};observed_.reset();
        // 1c's local Applied means STAGED here. No SDK input changes until tick.
        return ApplyResult::Applied;
    }
    bool tick(const Interval& i) override {
        if(!error_.empty() || !pending_ || pending_->interval.frame!=i.frame ||
           pending_->interval.begin!=i.begin || pending_->interval.end!=i.end)
            return fail("missing or mismatched stage");
        if(!clear_readback())return fail("effort changed outside owner");
        const Pending p=*pending_;pending_.reset(); // single use before physics
        for(unsigned w=0;w<4;++w) {
            vehicle_.setSteerAngle(order_[w],static_cast<float>(p.effort.steer_right_rad[w]));
            vehicle_.setDriveTorque(order_[w],static_cast<float>(p.effort.motor_nm[w]));
            vehicle_.setBrakeTorque(order_[w],static_cast<float>(p.effort.friction_nm[w]));
        }
        try {
            for(unsigned w=0;w<4;++w)if(vehicle_.getSteerAngle(order_[w])!=p.effort.steer_right_rad[w] ||
                vehicle_.getDriveTorque(order_[w])!=p.effort.motor_nm[w] ||
                vehicle_.getBrakeTorque(order_[w])!=p.effort.friction_nm[w])return fail("effort readback mismatch");
            if(!step_())return fail("physics result unavailable/ambiguous");
            std::array<double,4> omega{};
            for(unsigned w=0;w<4;++w) {
                omega[w]=vehicle_.mWheelsDynData.getWheelRotationSpeed(order_[w]);
                if(!std::isfinite(omega[w]))return fail("nonfinite wheel observation");
            }
            observed_=Observation{p.actual,p.interval,p.effort,omega,vehicle_.getRigidDynamicActor()->isSleeping(),false};
            last_end_=i.end;++completed_;clear();return true;
        } catch(...) {fail("physics exception/ambiguous");throw;}
    }
    bool fail(const char* reason) {error_=reason;pending_.reset();observed_.reset();clear();return false;}
    bool clear_readback() const {
        for(unsigned w=0;w<4;++w)if(vehicle_.getDriveTorque(w)!=0 || vehicle_.getBrakeTorque(w)!=0 || vehicle_.getSteerAngle(w)!=0)return false;
        return true;
    }
    void clear() {
        for(unsigned w=0;w<4;++w) {vehicle_.setDriveTorque(w,0);vehicle_.setBrakeTorque(w,0);vehicle_.setSteerAngle(w,0);}
    }
    physx::PxVehicleNoDrive& vehicle_;
    const m7_effort::Mapping mapping_;
    const std::array<unsigned,4> order_;
    const Step step_;
    std::optional<Pending> pending_;
    std::optional<Observation> observed_;
    std::string error_;
    Time last_end_=0;
    unsigned completed_=0;
    inline static std::mutex registry_mutex_;
    inline static std::set<const physx::PxVehicleNoDrive*> registry_;
};
} // namespace stratadrive::m7_nodrive

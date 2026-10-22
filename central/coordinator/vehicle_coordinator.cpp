#include "vehicle_coordinator.hpp"

#include <algorithm>
#include <limits>

namespace stratadrive::central {
namespace {
constexpr std::uint64_t kPeriod=10000000ULL, kGap=30000000ULL;
VehicleManagementConfig management_config(CoordinatorExecution e) { VehicleManagementConfig c; if(e.external_releases) c.minimum_tick_interval_ns=1000000; return c; }
AllocationConfig allocation_config(CoordinatorExecution e) { AllocationConfig c; c.minimum_tick_interval_ns=e.external_releases?1000000:allocation_period(e.renewal); return c; }
NormalStopConfig stop_config(CoordinatorExecution e) { NormalStopConfig c; if(e.external_releases) c.minimum_tick_interval_ns=1000000; return c; }
}
VehicleCoordinator::VehicleCoordinator(CoordinatorPort& port,CoordinatorExecution e):port_(port),execution_(e),management_(management_config(e)),allocation_(allocation_config(e)),stop_(stop_config(e)) {}
bool VehicleCoordinator::start_session(CoordinatorSession session) {
    if(session.epoch==0 || session.epoch<=epoch_ || (epoch_!=0 && session.enable_ns<observed_ns_)) return false;
    if(!port_.session_ready(session)) return false;
    const auto now=port_.now_ns();
    if(now<session.enable_ns || (epoch_!=0 && now<observed_ns_) || now==std::numeric_limits<std::uint64_t>::max()) return false;
    // These owners are private and always initialized together. The preflight
    // above cannot reset a remote participant or clear an existing fault.
    if(!management_.start_session(session.epoch,session.enable_ns) || !allocation_.start_session(session.epoch,session.enable_ns) ||
        !stop_.start_session(session.epoch,session.enable_ns)) return false;
    epoch_=session.epoch; enable_ns_=session.enable_ns; observed_ns_=now;
    tick_ns_.reset(); allocation_ns_.reset(); lifecycle_.reset(); vehicle_.reset(); last_power_.reset(); pending_handoff_.reset(); fault_=CoordinatorFault::None;
    normal_armed_=stopping_=protection_selected_=protection_attempted_=in_cycle_=false; return true;
}
void VehicleCoordinator::fail(CoordinatorFault fault) {
    const bool first=fault_==CoordinatorFault::None;
    if(first || fault==CoordinatorFault::ClockError) fault_=fault;
    normal_armed_=false;
    if(first) { management_.mark_continuity_lost(observed_ns_); allocation_.mark_continuity_lost(observed_ns_); }
    if(!protection_selected_ && !protection_attempted_) { protection_attempted_=true; protection_selected_=port_.protect(); }
}
bool VehicleCoordinator::advance(std::uint64_t now) {
    if(epoch_==0) return false;
    if(now<observed_ns_ || now==std::numeric_limits<std::uint64_t>::max()) { fail(CoordinatorFault::ClockError); return false; }
    observed_ns_=now;
    if(now-tick_ns_.value_or(enable_ns_)>kGap) fail(CoordinatorFault::ControlDeadline);
    return fault_==CoordinatorFault::None;
}
bool VehicleCoordinator::checkpoint() {
    if(!advance(port_.now_ns())) return false;
    if(in_cycle_ && observed_ns_-cycle_start_ns_>kGap) { fail(CoordinatorFault::ControlDeadline); return false; }
    return true;
}
bool VehicleCoordinator::accept_lifecycle(const LifecycleRequest& root) {
    const auto accepted=management_.receive_request(root,observed_ns_);
    if(accepted!=LifecycleReceiveDecision::Accepted && accepted!=LifecycleReceiveDecision::Unchanged) {
        if(management_.decision().fault!=VehicleManagementFault::None) fail(CoordinatorFault::Management);
        return false;
    }
    if(accepted==LifecycleReceiveDecision::Accepted) {
        lifecycle_=root;
        if(!port_.authorize_lifecycle(root)) { fail(CoordinatorFault::RequestDelivery); return false; }
    }
    return checkpoint();
}
bool VehicleCoordinator::accept_vehicle(const VehicleRequest& root) {
    const auto accepted=allocation_.receive_request(root,observed_ns_);
    if(accepted!=AllocationReceiveDecision::Accepted && accepted!=AllocationReceiveDecision::Unchanged) {
        if(allocation_.decision().protection_required) fail(CoordinatorFault::Allocation);
        return false;
    }
    if(accepted==AllocationReceiveDecision::Accepted) {
        vehicle_=root;
        if(!port_.authorize_vehicle(root)) { fail(CoordinatorFault::RequestDelivery); return false; }
    }
    return checkpoint();
}
CoordinatorReceive VehicleCoordinator::receive_lifecycle(const LifecycleRequest& root,std::uint64_t now) {
    if(epoch_==0) return CoordinatorReceive::NotInitialized;
    if(!advance(now) || !checkpoint()) return CoordinatorReceive::Latched;
    if(stopping_) return CoordinatorReceive::Stopping;
    if(normal_armed_ && root.action!=can::BmsPowerAction::Enable) return CoordinatorReceive::StopRequired;
    const auto previous=lifecycle_;
    if(!accept_lifecycle(root)) return fault_==CoordinatorFault::None?CoordinatorReceive::Rejected:CoordinatorReceive::Latched;
    return previous && previous->identity.sequence==root.identity.sequence?CoordinatorReceive::Unchanged:CoordinatorReceive::Accepted;
}
CoordinatorReceive VehicleCoordinator::receive_vehicle(const VehicleRequest& root,std::uint64_t now) {
    if(epoch_==0) return CoordinatorReceive::NotInitialized;
    if(!advance(now) || !checkpoint()) return CoordinatorReceive::Latched;
    if(stopping_) return CoordinatorReceive::Stopping;
    if(!normal_armed_ || !management_.decision().normal_allowed) return CoordinatorReceive::NotReady;
    const auto previous=vehicle_;
    if(!accept_vehicle(root)) return fault_==CoordinatorFault::None?CoordinatorReceive::Rejected:CoordinatorReceive::Latched;
    return previous && previous->sequence==root.sequence?CoordinatorReceive::Unchanged:CoordinatorReceive::Accepted;
}
CoordinatorReceive VehicleCoordinator::receive_stop(const NormalStopRequest& root,std::uint64_t now) {
    if(epoch_==0) return CoordinatorReceive::NotInitialized;
    if(!advance(now) || !checkpoint()) return CoordinatorReceive::Latched;
    if(stopping_) {
        const auto result=stop_.receive_request(root,observed_ns_);
        if(result==StopReceiveResult::Latched) { fail(CoordinatorFault::Stop); return CoordinatorReceive::Latched; }
        return result==StopReceiveResult::Accepted?CoordinatorReceive::Accepted:result==StopReceiveResult::Unchanged?CoordinatorReceive::Unchanged:CoordinatorReceive::Rejected;
    }
    if(!normal_armed_ || !management_.decision().normal_allowed || !lifecycle_ || !vehicle_) return CoordinatorReceive::NotReady;
    if(lifecycle_->identity.sequence==std::numeric_limits<std::uint32_t>::max() || vehicle_->sequence==std::numeric_limits<std::uint32_t>::max()) {
        fail(CoordinatorFault::Stop); return CoordinatorReceive::Latched;
    }
    if(!stop_.begin(root,{lifecycle_->identity.sequence+1,vehicle_->sequence+1},observed_ns_)) return CoordinatorReceive::Rejected;
    stopping_=true; return CoordinatorReceive::Accepted;
}
void VehicleCoordinator::request_protection(std::uint64_t now) {
    if(epoch_!=0) { advance(now); fail(CoordinatorFault::LocalProtection); }
}
std::uint64_t VehicleCoordinator::next_allocation_ns() const {
    const auto previous=allocation_ns_.value_or(enable_ns_);
    const auto period=allocation_period(execution_.renewal);
    return previous>std::numeric_limits<std::uint64_t>::max()-period?std::numeric_limits<std::uint64_t>::max():previous+period;
}
bool VehicleCoordinator::allocate(const NormalDriveReadinessInputs& in) {
    if(!last_power_ || !port_.allocation_ready(*last_power_,next_allocation_ns())) {
        allocation_.poll(observed_ns_);
        if(allocation_.decision().protection_required) fail(CoordinatorFault::Allocation);
        return false;
    }
    if(in.epoch!=epoch_ || in.session_enable_ns!=enable_ns_) { fail(CoordinatorFault::SessionMismatch); return false; }
    const auto received_parent=port_.received_permission_parent();
    AllocationInputs inputs{in,management_.decision(),port_.current_permission(),received_parent?received_parent:last_power_->permission_parent};
    if(!checkpoint()) return false;
    record_allocation_release();
    const auto commands=allocation_.tick(inputs,observed_ns_);
    if(allocation_.decision().protection_required) { fail(CoordinatorFault::Allocation); return false; }
    if(commands && !port_.deliver_commands(*commands)) { fail(CoordinatorFault::CommandDelivery); return false; }
    return checkpoint();
}
void VehicleCoordinator::record_allocation_release() {
    const auto period=allocation_period(execution_.renewal);
    allocation_ns_=execution_.external_releases?enable_ns_+((observed_ns_-enable_ns_)/period)*period:observed_ns_;
}
OperationStatus VehicleCoordinator::progress_handoff() {
    if(!pending_handoff_ || !port_.commands_settled()) return OperationStatus::Pending;
    const auto plan=*pending_handoff_;
    if(!allocation_.select_normal_stop(plan.lease,observed_ns_)) return OperationStatus::Rejected;
    const auto status=port_.stop_status(plan);
    if(!checkpoint()) return OperationStatus::Rejected;
    if(status==OperationStatus::Accepted) {
        if(plan.state==NormalStopState::HandoffPending && !stop_.acknowledge_handoff(plan.lease,observed_ns_)) return OperationStatus::Rejected;
        pending_handoff_.reset(); normal_armed_=false;
    }
    return status;
}
bool VehicleCoordinator::tick(const NormalDriveReadinessInputs& in,std::uint64_t now,bool management_release) {
    if(epoch_==0) return false;
    if(!management_release || (tick_ns_ && now>=*tick_ns_ && now-*tick_ns_<(execution_.external_releases?1000000ULL:kPeriod))) {
        if(!advance(now)) return false;
        if(pending_handoff_) {
            if(progress_handoff()==OperationStatus::Rejected) fail(CoordinatorFault::Handoff);
            return true;
        }
        if(now<next_allocation_ns() ||
            stop_.decision().state==NormalStopState::HandoffPending || stop_.decision().state==NormalStopState::PowerDown ||
            stop_.decision().state==NormalStopState::Complete) return false;
        if(!normal_armed_) {
            record_allocation_release();
            allocation_.tick({in,management_.decision(),std::nullopt,std::nullopt},observed_ns_);
            if(allocation_.decision().protection_required) fail(CoordinatorFault::Allocation);
            return true;
        }
        // Resume only the independent allocator after an asynchronous grant
        // ingress. Do not rerun VM, issue a new grant or refresh an old root.
        cycle_start_ns_=observed_ns_; in_cycle_=true;
        if(!port_.healthy(epoch_)) fail(CoordinatorFault::LocalProtection);
        const bool ran=fault_==CoordinatorFault::None && checkpoint() && allocate(in);
        in_cycle_=false; return ran;
    }
    protection_attempted_=false;
    advance(now);
    if(!tick_ns_ || now>=*tick_ns_) tick_ns_=now;
    cycle_start_ns_=observed_ns_; in_cycle_=true;
    const auto finish=[&] { in_cycle_=false; return true; };
    if(fault_!=CoordinatorFault::None) { fail(fault_); return finish(); }
    if(!checkpoint()) return finish();
    if(in.epoch!=epoch_ || in.session_enable_ns!=enable_ns_) { fail(CoordinatorFault::SessionMismatch); return finish(); }
    if(!port_.healthy(epoch_)) { fail(CoordinatorFault::LocalProtection); return finish(); }
    if(!checkpoint()) return finish();
    if(pending_handoff_) {
        const auto status=progress_handoff();
        if(status==OperationStatus::Rejected) fail(CoordinatorFault::Handoff);
        if(status!=OperationStatus::Accepted) return finish();
    }
    std::optional<NormalStopPlan> plan;
    // A stop arriving beside a newly accepted normal root waits until the next
    // source instant. It must not emit a child with the same source time or
    // issue another propulsive normal command while waiting.
    const bool stop_ready=stopping_ && (!lifecycle_ || observed_ns_>lifecycle_->identity.source_time_ns) && (!vehicle_ || observed_ns_>vehicle_->source_time_ns);
    if(stop_ready) {
        plan=stop_.tick(in,management_.decision(),observed_ns_);
        if(stop_.decision().protection_required || (plan && !accept_lifecycle(plan->lifecycle))) { fail(CoordinatorFault::Stop); return finish(); }
    }
    const auto power=management_.tick(in,observed_ns_);
    if(management_.decision().fault!=VehicleManagementFault::None) { fail(CoordinatorFault::Management); return finish(); }
    if(power) {
        last_power_=power;
        port_.observe_permission(management_.decision().permission_support,power->drive_permission);
        if(management_.decision().normal_allowed && !normal_armed_) {
            const auto arm=port_.arm_status(epoch_);
            if(arm==OperationStatus::Rejected) { fail(CoordinatorFault::Arm); return finish(); }
            if(arm==OperationStatus::Pending) {
                // The allocation owner still executes its waiting runnable;
                // pending arm is not a reason to suspend its deadline monitor.
                // No permission is supplied and no normal output can be issued.
                if(observed_ns_>=next_allocation_ns()) {
                    record_allocation_release();
                    allocation_.tick({in,management_.decision(),std::nullopt,std::nullopt},observed_ns_);
                    if(allocation_.decision().protection_required) fail(CoordinatorFault::Allocation);
                }
                return finish();
            }
            normal_armed_=true;
        }
        if(!checkpoint()) return finish();
        if(!port_.deliver_power(*power)) { fail(CoordinatorFault::PowerDelivery); return finish(); }
        if(!checkpoint()) return finish();
    }
    // A sub-owner can be early after callback jitter. Do not republish its old
    // output; still service the independent allocation runnable.
    const bool terminal=stop_.decision().state==NormalStopState::PowerDown || stop_.decision().state==NormalStopState::Complete;
    if(stopping_ && plan && plan->vehicle && !plan->handoff_required && !accept_vehicle(*plan->vehicle)) { fail(CoordinatorFault::Allocation); return finish(); }
    if(!terminal && (!stopping_ || (plan && !plan->handoff_required)) && observed_ns_>=next_allocation_ns()) {
        allocate(in); if(fault_!=CoordinatorFault::None) return finish();
    }
    if(plan && plan->handoff_required) {
        pending_handoff_=plan;
        if(progress_handoff()==OperationStatus::Rejected) fail(CoordinatorFault::Handoff);
    }
    return finish();
}
CoordinatorDecision VehicleCoordinator::decision() const {
    return {fault_,normal_armed_,stopping_,protection_selected_,management_.decision(),allocation_.decision(),stop_.decision()};
}
}  // namespace stratadrive::central

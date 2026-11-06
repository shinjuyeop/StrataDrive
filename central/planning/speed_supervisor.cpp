#include "speed_supervisor.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
namespace {
bool same(const PlannerProposal& a,const PlannerProposal& b) noexcept {
    return a.schema==b.schema && a.epoch==b.epoch && a.clock_instance==b.clock_instance && a.sequence==b.sequence &&
        a.model_revision==b.model_revision && a.source_ns==b.source_ns && a.expires_ns==b.expires_ns &&
        a.history_ns==b.history_ns && a.speed_mps==b.speed_mps && a.speed_limit_mps==b.speed_limit_mps && a.risk==b.risk && a.valid==b.valid;
}
bool speed_valid(double v) noexcept {return std::isfinite(v) && v>=0 && v<=SpeedPI::kMaxTargetMps;}
}
std::optional<PlannerProposal> bind_speed_proposal(const PlannerInput& input,const ModelSpeedOutput& output,
    std::uint64_t sequence,std::uint64_t revision) noexcept {
    if(!input.valid || !input.epoch || !input.clock_instance || !sequence || !revision || !output.valid ||
       !std::isfinite(output.risk) || output.risk<0 || output.risk>1 ||
       !std::all_of(output.speed_mps.begin(),output.speed_mps.end(),speed_valid))return std::nullopt;
    for(std::size_t i=0;i<input.history.size();++i) {
        const auto& s=input.history[i];
        if(!speed_valid(s.speed_mps) || !speed_valid(s.route_speed_mps) ||
           !std::isfinite(s.propulsion_n) || s.propulsion_n<0 || !std::isfinite(s.braking_n) || s.braking_n<0 ||
           !std::isfinite(s.road_load_min_n) || !std::isfinite(s.road_load_max_n) || s.road_load_min_n>s.road_load_max_n ||
           (i && (input.source_ns[i]<=input.source_ns[i-1] || input.source_ns[i]-input.source_ns[i-1]!=SpeedPI::kPeriodNs)))return std::nullopt;
    }
    const auto source=input.source_ns.back();
    if(source>std::numeric_limits<std::uint64_t>::max()-30000001)return std::nullopt;
    PlannerProposal p;p.epoch=input.epoch;p.clock_instance=input.clock_instance;p.sequence=sequence;p.model_revision=revision;
    p.source_ns=source;p.expires_ns=source+30000001;p.history_ns=input.source_ns;p.speed_mps=output.speed_mps;p.speed_limit_mps=input.history.back().route_speed_mps;p.risk=output.risk;p.valid=true;
    return p;
}
SpeedSupervisor::SpeedSupervisor(double risk):maximum_risk_(risk) {
    if(!std::isfinite(risk) || risk<0 || risk>1) throw std::invalid_argument("supervisor risk threshold");
}
bool SpeedSupervisor::start_session(std::uint32_t epoch,std::uint64_t clock,std::uint64_t enable) noexcept {
    if(epoch<=epoch_ || !clock || (clock==clock_ && enable<last_now_)) return false;
    epoch_=epoch;clock_=clock;enable_=enable;last_now_=enable;previous_.reset();return true;
}
SupervisedSpeed SpeedSupervisor::select(std::uint64_t now,const std::optional<PlannerProposal>& proposal,
    const ClassicalSpeedProposal& fallback,bool permission) noexcept {
    if(!epoch_ || now<enable_ || now<last_now_ || !permission) return {ProposalSource::Protection,ProposalReason::Authority,std::nullopt,0,0};
    last_now_=now;
    ProposalReason reason=ProposalReason::Missing;
    if(proposal) {
        const auto& p=*proposal;
        reason=ProposalReason::Invalid;
        bool shape=p.valid && p.schema==PlannerProposal::kSchema && p.model_revision && p.sequence &&
            std::isfinite(p.risk) && p.risk>=0 && p.risk<=1 &&
            speed_valid(p.speed_limit_mps) && std::all_of(p.speed_mps.begin(),p.speed_mps.end(),[&](double v){return speed_valid(v) && v<=p.speed_limit_mps;});
        for(std::size_t i=1;i<p.history_ns.size();++i)
            shape=shape && p.history_ns[i]>p.history_ns[i-1] && p.history_ns[i]-p.history_ns[i-1]==20000000;
        shape=shape && p.history_ns.back()==p.source_ns && p.history_ns.front()>=enable_;
        // No trajectory jump hidden beyond the first sample. The dynamic force
        // governor still checks the selected speed against CURRENT capacity.
        for(std::size_t i=1;i<p.speed_mps.size();++i) {
            const double a=(p.speed_mps[i]-p.speed_mps[i-1])/0.1;
            shape=shape && a>=SpeedPI::kLowMps2 && a<=SpeedPI::kHighMps2;
        }
        if(shape) {
            if(p.epoch!=epoch_ || p.clock_instance!=clock_ ||
                (previous_ && (p.model_revision!=previous_->model_revision || p.sequence<previous_->sequence ||
                    (p.sequence==previous_->sequence && !same(p,*previous_)) ||
                    (p.sequence>previous_->sequence && p.source_ns<=previous_->source_ns)))) reason=ProposalReason::Identity;
            else if(p.source_ns>now || now-p.source_ns>30000000 || p.expires_ns<=now ||
                    p.expires_ns-p.source_ns>30000001) reason=ProposalReason::Stale;
            else {
                previous_=p;
                if(p.risk>maximum_risk_) return {ProposalSource::Protection,ProposalReason::Hazard,std::nullopt,0,0};
                const auto index=static_cast<std::size_t>((now-p.source_ns)/100000000);
                return {ProposalSource::Learned,ProposalReason::Accepted,p.speed_mps[index],p.source_ns,p.expires_ns};
            }
        }
    }
    if(fallback.valid && fallback.epoch==epoch_ && fallback.clock_instance==clock_ && speed_valid(fallback.speed_mps) &&
       fallback.source_ns>=enable_ && fallback.source_ns<=now && now-fallback.source_ns<=30000000 &&
       fallback.expires_ns>now && fallback.expires_ns-fallback.source_ns<=30000001)
        return {ProposalSource::Classical,reason,fallback.speed_mps,fallback.source_ns,fallback.expires_ns};
    return {ProposalSource::Protection,ProposalReason::NoFallback,std::nullopt,0,0};
}
SupervisedSpeedRequest::SupervisedSpeedRequest(ReferenceConfig c,double radius)
    :config_(c),radius_(radius),governor_(c),controller_(radius,true) {}
bool SupervisedSpeedRequest::start_session(std::uint32_t epoch,std::uint64_t clock,std::uint64_t enable) noexcept {
    // Validate on copies so a rejected INIT cannot partially reset ownership.
    auto s=supervisor_;auto g=governor_;auto c=controller_;
    if(!s.start_session(epoch,clock,enable) || !g.start_session(epoch,enable) || !c.start_session(epoch,enable)) return false;
    // Supervisor has a const configuration; reconstructing is unnecessary.
    supervisor_.start_session(epoch,clock,enable);governor_.start_session(epoch,enable);controller_.start_session(epoch,enable);
    decision_={};reference_.reset();last_dependency_.reset();latched_=false;
    epoch_=epoch;clock_=clock;enable_=enable;fault_.reset();success_.reset();return true;
}
std::optional<DerivedVehicleRequest> SupervisedSpeedRequest::step(std::uint64_t now,const std::optional<PlannerProposal>& p,
    const ClassicalSpeedProposal& fallback,const std::optional<can::DriveMessage>& current,const std::optional<AvailableForce>& force,
    bool permission,std::optional<PropulsionSelection> selection) noexcept {
    if(latched_) return std::nullopt;
    decision_=supervisor_.select(now,p,fallback,permission);reference_.reset();
    const auto fail=[&](ProposalReason reason)->std::optional<DerivedVehicleRequest>{
        decision_.source=ProposalSource::Protection;decision_.reason=reason;decision_.target_mps.reset();latched_=true;
        success_.reset();fault_=SupervisedSpeedFault{epoch_,clock_,enable_,now,reason,governor_.fault()};return std::nullopt;
    };
    if(!decision_.target_mps) return fail(decision_.reason);
    if(!force) return fail(ProposalReason::CapacityInput);
    if(!current || !current->wheel_speed) return fail(ProposalReason::Reference);
    const auto& wheel=*current->wheel_speed;
    reference_=governor_.step(now,*decision_.target_mps,{current->epoch,wheel.source_time_ns,wheel.source_time_ns,wheel.value_rad_s*radius_},*force);
    if(!reference_) return fail(ProposalReason::Reference);
    auto request=controller_.step_derived(now,reference_->target_mps,current,permission,selection);
    if(!request) return fail(ProposalReason::Controller);
    if(force->profile==ForceProfile::ReceiverPowerLimits) {
        request->input.source_time_ns=std::min(request->input.source_time_ns,decision_.oldest_source_ns);
        request->input.power=PowerInputDependency{force->source_ns,force->expires_ns};
    } else request->input.source_time_ns=std::min({request->input.source_time_ns,reference_->oldest_source_ns,decision_.oldest_source_ns});
    request->input.expires_at_ns=std::min({request->input.expires_at_ns,reference_->expires_ns,decision_.expires_ns});
    request->request.expires_at_ns=std::min(request->request.expires_at_ns,request->input.expires_at_ns);
    const auto oldest=std::min(request->input.source_time_ns,reference_->oldest_source_ns);
    if(request->request.expires_at_ns<=now || (last_dependency_ && oldest<=*last_dependency_))
        return fail(ProposalReason::Reference);
    last_dependency_=oldest;
    success_=SupervisedSpeedSuccess{epoch_,clock_,enable_,now,*current,*force,*request};
    return request;
}
} // namespace stratadrive::central

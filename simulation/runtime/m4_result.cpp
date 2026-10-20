#include "m4_owner_network.hpp"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <string_view>

namespace stratadrive::simulation::m4_detail {
M4Timing Audit::result(std::string name) {
        M4Timing r; r.owner=std::move(name); r.samples=durations.size(); r.audit_buffer_growths=buffer_growths; if(durations.empty()) return r;
        std::sort(durations.begin(),durations.end()); double sum=0;
        for(const auto d:durations) { sum+=static_cast<double>(d); if(d>4000000) ++r.body_over_4ms; }
        const auto count=static_cast<double>(durations.size());
        const auto percentile=[&](double p) { return static_cast<double>(durations[static_cast<std::size_t>(std::ceil(p*count))-1])/1000; };
        r.mean_body_us=sum/count/1000; r.p95_body_us=percentile(.95); r.p99_body_us=percentile(.99);
        r.max_body_us=static_cast<double>(durations.back())/1000; r.max_poll_gap_ms=static_cast<double>(poll_gap)/kMs; r.max_runnable_gap_ms=static_cast<double>(runnable_gap)/kMs;
        return r;
    }
M4Result Network::finish() {
        collect_filters();
        for(const auto& log:transport_logs) {
            result.event_overflow=result.event_overflow || log.overflow;
            result.transport_events.insert(result.transport_events.end(),log.rows.begin(),log.rows.end());
        }
        std::stable_sort(result.transport_events.begin(),result.transport_events.end(),[](const auto& a,const auto& b){return a.time_ns<b.time_ns;});
        if(execution_watch) { const auto rows=execution_watch->rows(); result.execution.insert(result.execution.end(),rows.begin(),rows.end()); }
        for(const auto& row:result.execution) {
            if(!row.end_ns || row.end_ns>row.deadline_ns) ++result.deadline_misses;
            if(!row.start_ns) ++result.skipped_opportunities;
        }
        result.timing_ok=result.deadline_misses==0;
        for(const auto& log:owner_events) result.events.insert(result.events.end(),log.begin(),log.end());
        for(const auto& leaf:leaf_owners) result.events.insert(result.events.end(),leaf->input_events().begin(),leaf->input_events().end());
        std::stable_sort(result.events.begin(),result.events.end(),[](const auto& a,const auto& b){ return a.time_ns<b.time_ns; });
        result.physical_ok=physical.ok(); result.completed_batches=port.completed_batches(); result.front_frames=zone_owners[0]->command_frames(); result.rear_frames=zone_owners[1]->command_frames();
        const std::array<const char*,10> names{"FrontZone","RearZone","Steering","Brake","Drive","Bms","Power","Central","Physical","Monitor"};
        for(std::size_t i=0;i<(config.execution_guards?10U:9U);++i) { result.ownership_ok=result.ownership_ok && audit[i].valid; result.timing.push_back(audit[i].result(names[i])); }
        std::size_t c=0;
        for(auto row:physical.trace) {
            while(c+1<central_trace.size() && central_trace[c+1].source_ns<=row.source_ns) ++c;
            if(!central_trace.empty() && central_trace[c].source_ns<=row.source_ns) {
                const auto& s=central_trace[c]; row.central_observation_ns=s.source_ns;
                if(!row.run_gate || row.epoch==s.epoch) { row.epoch=s.epoch; row.normal_armed=s.normal_armed; row.protected_all=s.protected_all;
                row.management=s.management; row.coordinator_fault=s.coordinator_fault; row.stop_state=s.stop_state;
                row.steering_source_ns=s.steering_source_ns; row.brake_source_ns=s.brake_source_ns; row.drive_source_ns=s.drive_source_ns;
                row.command_source_ns=s.command_source_ns; row.command_root_sequence=s.command_root_sequence;
                } // A newer physical gate cannot inherit an older epoch's protection/arm snapshot.
            }
            if(!result.trace.empty()) {
                const auto& old=result.trace.back();
                if(row.source_ns<=old.source_ns || row.model_epoch!=old.model_epoch || row.model_sequence<=old.model_sequence || row.energy_j>old.energy_j+1e-6 || row.soc>old.soc+1e-12) result.model_preserved=false;
            }
            result.trace.push_back(row);
        }
        const auto d=core.decision(); const bool expected_fault=config.scenario==M4Scenario::PartialFront || config.scenario==M4Scenario::FeedbackLoss || config.scenario==M4Scenario::CommandLoss || config.scenario==M4Scenario::PartialArm || config.scenario==M4Scenario::Rejoin;
        bool scenario_ok;
        if(expected_fault) scenario_ok=result.first_fault_ns!=0 && result.all_protected_ns>=result.first_fault_ns && result.all_protected_ns-result.first_fault_ns<=100*kMs;
        else scenario_ok=result.first_fault_ns==0 && d.fault==central::CoordinatorFault::None && result.first_active_ns!=0;
        if(config.scenario==M4Scenario::Rejoin) scenario_ok=scenario_ok && result.rejoin_active_ns>config.rejoin_ns && d.fault==central::CoordinatorFault::None;
        if(expected_fault && config.scenario!=M4Scenario::PartialArm) scenario_ok=scenario_ok && result.first_fault_ns>=config.injection_ns && result.all_protected_ns<=config.injection_ns+100*kMs;
        if(config.scenario==M4Scenario::NormalStop) scenario_ok=scenario_ok && d.stop.state==central::NormalStopState::Complete && d.management.power_off_confirmed;
        if(config.scenario!=M4Scenario::PartialArm) scenario_ok=scenario_ok && result.completed_batches>0;
        if(config.scenario==M4Scenario::PartialArm) scenario_ok=scenario_ok && result.first_active_ns==0 && result.front_frames==0 && result.rear_frames==0;
        if(config.scenario==M4Scenario::Fault) {
            const auto is=[](const M4Event& e,const char* value){ return std::string_view(e.kind)==value; };
            bool affected=false,protected_live=false;
            for(const auto& e:result.events) {
                if(is(e,"owner-stopped") || is(e,"dropped") || is(e,"delayed") || is(e,"overflow") || is(e,"receive-blocked") || is(e,"overrun-injected")) {
                    affected=true; if(!result.effective_injection_ns) result.effective_injection_ns=e.time_ns-start;
                }
                if(result.effective_injection_ns && e.time_ns-start>=result.effective_injection_ns && (is(e,"fault-observed") || is(e,"session-failed") || is(e,"deadline-detected")) && !result.live_fault_ns) result.live_fault_ns=e.time_ns-start;
                if(is(e,"leaf-protection-selected") || is(e,"output-watchdog")) protected_live=true;
                for(const auto& f:config.faults) if(f.path==FaultPath::Owner && f.kind==FaultKind::Pause && e.owner==static_cast<std::size_t>(f.target) && f.active(e.time_ns-start) && (is(e,"fault-observed") || is(e,"leaf-protection-selected") || is(e,"zone-protection-ack"))) ++result.stopped_ack_violations;
            }
            for(const auto& row:result.trace) {
                if(row.protected_all && row.run_gate) result.gate_latched=false;
                if(result.effective_injection_ns && row.elapsed_ns>=result.effective_injection_ns && !row.run_gate && !result.normal_blocked_ns) result.normal_blocked_ns=row.elapsed_ns;
                if(result.normal_blocked_ns && row.elapsed_ns>result.normal_blocked_ns && (!config.recovery_ns || row.elapsed_ns<config.recovery_ns) && row.run_gate) result.gate_latched=false;
            }
            for(const auto& e:result.events) if(is(e,"leaf-protection-selected") && e.epoch==config.first_epoch && result.effective_injection_ns && e.time_ns-start>=result.effective_injection_ns && e.time_ns-start<=result.effective_injection_ns+100*kMs) result.live_selection_mask|=1U<<e.owner;
            result.missing_selection_mask=124U & ~result.live_selection_mask;
            bool early_fault=false;
            for(const auto& e:result.events) if((is(e,"fault-observed") || is(e,"deadline-detected") || is(e,"session-failed")) && e.time_ns-start<result.effective_injection_ns) early_fault=true;
            scenario_ok=affected && !early_fault && result.gate_latched && result.stopped_ack_violations==0 && (protected_live || result.first_active_ns==0) && result.live_fault_ns && result.normal_blocked_ns;
            const bool preparing=std::any_of(config.faults.begin(),config.faults.end(),[](const auto& f){return f.phase==FaultPhase::Prepare;});
            if(!preparing && result.effective_injection_ns) scenario_ok=scenario_ok && result.live_fault_ns<=result.effective_injection_ns+100*kMs && result.normal_blocked_ns<=result.effective_injection_ns+100*kMs;
            if(config.recovery_ns) scenario_ok=scenario_ok && result.rejoin_active_ns>config.recovery_ns && d.fault==central::CoordinatorFault::None;
        }
        if(config.execution_guards && !expected_fault && config.scenario!=M4Scenario::Fault) scenario_ok=scenario_ok && result.timing_ok;
        result.passed=result.startup_ok && scenario_ok && result.physical_ok && result.ownership_ok && !result.event_overflow && result.model_preserved;
        if(!result.passed) result.reason="scenario="+std::string(m4_scenario_name(config.scenario))+" core="+std::to_string(static_cast<int>(d.fault))+" session="+std::to_string(static_cast<int>(startup.fault()))+" management="+std::to_string(static_cast<int>(d.management.state))+" vm_fault="+std::to_string(static_cast<int>(d.management.fault))+" allocation="+std::to_string(static_cast<int>(d.allocation.fault))+" stop="+std::to_string(static_cast<int>(d.stop.state))+" physical="+std::to_string(result.physical_ok)+" active="+std::to_string(result.first_active_ns)+" fault="+std::to_string(result.first_fault_ns)+" selected="+std::to_string(result.all_protected_ns);
        if(!result.passed) { result.reason+=" transport="+std::to_string(static_cast<int>(port.fault()))+" op="+std::to_string(port.failed_operation())+" front="+std::to_string(zone_owners[0]->rejection())+" rear="+std::to_string(zone_owners[1]->rejection())+" energy="+std::to_string(physical.fault_code()); for(const auto& l:leaf_owners) result.reason+=" leaf="+std::to_string(l->fault_code()); }
        return result;
    }
} // namespace stratadrive::simulation::m4_detail
namespace stratadrive::simulation {
void write_m4_result(const M4Config& config,const M4Result& r,const std::string& directory) {
    std::filesystem::create_directories(directory); const auto prefix=std::filesystem::path(directory)/(std::string(config.wall_time?"wall-":"logical-")+m4_scenario_name(config.scenario));
    std::ofstream csv(prefix.string()+".csv"); csv<<"elapsed_ms,source_ns,epoch,run_gate,normal_armed,protected_all,management,coordinator_fault,stop_state,angle_rad,pressure_pa,torque_nm,bus_v,soc,steering_source_ns,brake_source_ns,drive_source_ns,command_source_ns,command_root_sequence,central_observation_ns,energy_j,model_epoch,model_sequence,contacts\n"<<std::setprecision(12);
    for(const auto& row:r.trace) csv<<static_cast<double>(row.elapsed_ns)/m4_detail::kMs<<','<<row.source_ns<<','<<row.epoch<<','<<row.run_gate<<','<<row.normal_armed<<','<<row.protected_all<<','<<row.management<<','<<row.coordinator_fault<<','<<row.stop_state<<','<<row.angle_rad<<','<<row.pressure_pa<<','<<row.torque_nm<<','<<row.bus_v<<','<<row.soc<<','<<row.steering_source_ns<<','<<row.brake_source_ns<<','<<row.drive_source_ns<<','<<row.command_source_ns<<','<<row.command_root_sequence<<','<<row.central_observation_ns<<','<<row.energy_j<<','<<row.model_epoch<<','<<row.model_sequence<<','<<row.contacts<<'\n';
    if(config.transport_trace) {
        std::ofstream transport_csv(prefix.string()+"-transport.csv");
        transport_csv<<"time_ns,stage,owner,peer,epoch,token,operation,original_source_ns,inner_deadline_ns,sent_ns,envelope_deadline_ns,result_source_ns,payload_source_ns,outcome\n";
        for(const auto& e:r.transport_events)transport_csv<<e.time_ns<<','<<e.stage<<','<<e.owner<<','<<e.peer<<','<<e.epoch<<','<<e.token<<','<<e.operation<<','<<e.original_source_ns<<','<<e.inner_deadline_ns<<','<<e.sent_ns<<','<<e.deadline_ns<<','<<e.result_source_ns<<','<<e.payload_source_ns<<','<<e.outcome<<'\n';
    }
    std::ofstream guard(prefix.string()+"-execution.csv"); guard<<"owner,slot,release_ns,deadline_ns,start_ns,end_ns,cpu_ns,detected_ns,requested_wake_ns\n";
    for(const auto& j:r.execution) guard<<j.owner<<','<<j.slot<<','<<j.release_ns<<','<<j.deadline_ns<<','<<j.start_ns<<','<<j.end_ns<<','<<j.cpu_ns<<','<<j.detected_ns<<','<<j.requested_wake_ns<<'\n';
    std::ofstream events(prefix.string()+"-events.csv"); events<<"time_ns,elapsed_ms,kind,owner,epoch,source_ns,deadline_ns,reference_ns,code\n"<<std::setprecision(12);
    const auto origin=r.trace.empty()?0:r.trace.front().source_ns-r.trace.front().elapsed_ns;
    for(const auto& e:r.events) events<<e.time_ns<<','<<static_cast<double>(e.time_ns-origin)/m4_detail::kMs<<','<<e.kind<<','<<e.owner<<','<<e.epoch<<','<<e.source_ns<<','<<e.deadline_ns<<','<<e.reference_ns<<','<<e.code<<'\n';
    std::ofstream summary(prefix.string()+".json"); summary<<std::boolalpha<<std::setprecision(12)<<"{\"passed\":"<<r.passed<<",\"ownership_ok\":"<<r.ownership_ok<<",\"physical_ok\":"<<r.physical_ok<<",\"first_active_ns\":"<<r.first_active_ns<<",\"first_fault_ns\":"<<r.first_fault_ns<<",\"all_protected_ns\":"<<r.all_protected_ns<<",\"rejoin_active_ns\":"<<r.rejoin_active_ns<<",\"completed_batches\":"<<r.completed_batches<<",\"front_frames\":"<<r.front_frames<<",\"rear_frames\":"<<r.rear_frames<<",\"timing\":[";
    for(std::size_t i=0;i<r.timing.size();++i) {
        const auto& t=r.timing[i]; if(i) summary<<',';
        summary<<"{\"owner\":\""<<t.owner<<"\",\"samples\":"<<t.samples<<",\"mean_body_us\":"<<t.mean_body_us<<",\"p95_body_us\":"<<t.p95_body_us<<",\"p99_body_us\":"<<t.p99_body_us<<",\"max_body_us\":"<<t.max_body_us<<",\"body_over_4ms\":"<<t.body_over_4ms<<",\"max_poll_gap_ms\":"<<t.max_poll_gap_ms<<",\"max_runnable_gap_ms\":"<<t.max_runnable_gap_ms<<",\"audit_buffer_growths\":"<<t.audit_buffer_growths<<'}';
    }
    summary<<"],\"threads\":[";
    for(std::size_t i=0;i<r.threads.size();++i) {
        const auto& t=r.threads[i]; if(i) summary<<',';
        summary<<"{\"owner\":"<<t.owner<<",\"policy\":"<<t.policy<<",\"priority\":"<<t.priority<<",\"cpu\":"<<t.cpu<<",\"tid\":"<<t.tid<<",\"requested_cpu\":"<<t.requested_cpu<<",\"setup_error\":"<<t.setup_error<<",\"affinity\":[";
        for(std::size_t k=0;k<t.affinity.size();++k) { if(k) summary<<','; summary<<t.affinity[k]; } summary<<"]}";
    }
    summary<<"],\"transport_trace_enabled\":"<<config.transport_trace<<",\"guards_enabled\":"<<config.execution_guards<<",\"fifo_requested\":"<<config.fifo<<",\"startup_ok\":"<<r.startup_ok<<",\"timing_ok\":"<<r.timing_ok<<",\"deadline_misses\":"<<r.deadline_misses<<",\"skipped_opportunities\":"<<r.skipped_opportunities;
    summary<<",\"faults\":[";
    for(std::size_t i=0;i<config.faults.size();++i) {
        const auto& f=config.faults[i]; if(i) summary<<',';
        summary<<"{\"path\":\""<<fault_path_name(f.path)<<"\",\"kind\":\""<<fault_kind_name(f.kind)<<"\",\"target\":\""<<m4_owner_name(f.target)<<"\",\"start_ns\":"<<f.start_ns<<",\"duration_ns\":"<<f.duration_ns<<",\"delay_ns\":"<<f.delay_ns<<",\"phase\":"<<static_cast<int>(f.phase)<<'}';
    }
    summary<<"],\"duration_ns\":"<<config.duration_ns<<",\"recovery_ns\":"<<config.recovery_ns<<",\"gate_latched\":"<<r.gate_latched<<",\"stopped_ack_violations\":"<<r.stopped_ack_violations<<",\"replaced_links\":"<<r.replaced_links<<",\"event_overflow\":"<<r.event_overflow<<",\"effective_injection_ns\":"<<r.effective_injection_ns<<",\"live_fault_ns\":"<<r.live_fault_ns<<",\"normal_blocked_ns\":"<<r.normal_blocked_ns<<",\"live_selection_mask\":"<<r.live_selection_mask<<",\"missing_selection_mask\":"<<r.missing_selection_mask<<",\"model_preserved\":"<<r.model_preserved<<",\"reason\":"<<std::quoted(r.reason)<<"}\n";
}
} // namespace stratadrive::simulation

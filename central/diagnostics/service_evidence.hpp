#pragma once
#include "control_diagnostics.hpp"

namespace stratadrive::diagnostics {
// Trusted owner calls feedback() / current_sample(now) in this same cycle.
// Never supply last_accepted() history as current input. This adapter preserves
// the independent wheel/torque/pressure acquisition times and fails closed.
ServiceEvidence capture_service_evidence(ControlContext,Session,Stamp enable,
    const central::NormalDriveReadinessInputs&,Stamp now,bool normal_dispatch_inhibited) noexcept;
} // namespace stratadrive::diagnostics

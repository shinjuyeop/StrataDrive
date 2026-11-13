# M10 bounded endurance V3

V1 acceptance criteria and the V2 explicit WallRig horizon remain unchanged.
V2's first live setup failed before physical INIT at the original10000-job
TaskSchedule storage ceiling. It executed zero physical intervals and retained
six preparation frames. Its remaining cases were not run. Both original setup
failures remain in evidence and future-exclusion history.

V3 adds an explicit diagnostic storage option to TaskSchedule: default10000 jobs
remain unchanged; opt-in capacity is160000. M4ExecutionWatch enables it only for
the exact35s/305s diagnostic windows. Every original2ms release and4ms deadline
has its own preallocated slot; no rolling reset, batch stitching, lost slot or
changed expiry is permitted. Original deadlines and missed-job detection after
the former10000th-slot boundary are tested. The actual executable must complete
allocation/START/STOP preflight for both30s and300s without a CARLA server before
any further live attempt. That preflight is not counted as live endurance.

Declare a fresh three-case30s series with the same workload and unchanged
controller guards. Run the conditional continuous300s case only when all three
original paired audits and exact native replays pass. V1/V2 failures are not
relabelled as successes. All raw callbacks remain excluded from future evaluation.

"""M6 reference model v1. Binary64, explicit Euler PI, fixed 20ms sample.
No ECU/session authority is issued here; invalid output requests existing protection.
Python model is the design artifact. C++ controller equivalence belongs to M8.
"""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Sample:
    epoch: int
    sequence: int
    source_ns: int
    speed_mps: float

@dataclass(frozen=True)
class Output:
    acceleration: float | None
    valid: bool
    reason: str
    integral: float
    source_ns: int

class SpeedPI:
    period_ns=20_000_000
    max_age_ns=60_000_000
    kp=1.0
    ki=.2
    slew=2.0
    low=-5.0
    high=2.0

    def __init__(self):
        self.epoch=0;self.integral=0.;self.previous=0.;self.last_ns=None;self.sample=None;self.fault=False;self.target=None

    def initialize(self,epoch):
        if epoch<=self.epoch:return False
        self.epoch=epoch;self.integral=0.;self.previous=0.;self.last_ns=None;self.sample=None;self.fault=False;self.target=None
        return True

    def step(self,now_ns,target,sample,permission):
        reason=''
        if not self.epoch:reason='uninitialized'
        elif self.fault:reason='latched'
        elif self.last_ns is not None and now_ns-self.last_ns!=self.period_ns:reason='sample-time'
        elif not permission:reason='permission'
        elif not math.isfinite(target) or not 0<=target<=40/3.6:reason='target'
        elif sample is None or not math.isfinite(sample.speed_mps) or sample.speed_mps<0:reason='invalid-speed'
        elif sample.epoch!=self.epoch:reason='epoch'
        elif sample.source_ns>now_ns or now_ns-sample.source_ns>self.max_age_ns:reason='source-age'
        elif self.sample and (sample.sequence<self.sample.sequence or sample.source_ns<self.sample.source_ns or
             (sample.sequence==self.sample.sequence and sample!=self.sample) or
             (sample.sequence>self.sample.sequence and sample.source_ns<=self.sample.source_ns)):reason='identity'
        if reason:
            self.fault=True
            return Output(None,False,reason,self.integral,sample.source_ns if sample else 0)
        dt=self.period_ns*1e-9
        rate=0. if self.target is None else (target-self.target)/dt
        # 2-DOF reference feedforward. Braking preview covers the declared
        # 50ms actuator delay + 50ms held sensor + 20ms controller sample.
        # Original reference is unchanged for judging. No synthetic measurement.
        reference_for_control=max(0.,target+.12*min(0.,rate))
        error=reference_for_control-sample.speed_mps
        raw=rate+self.kp*error+self.integral
        bounded=max(self.low,min(self.high,raw))
        output=max(self.previous-self.slew*dt,min(self.previous+self.slew*dt,bounded))
        # Conditional integration covers both amplitude AND slew saturation.
        # Integrate when unconstrained, or when the error drives back into limits.
        if (raw-output)*error<=0:self.integral+=self.ki*error*dt
        self.target=target;self.last_ns=now_ns;self.previous=output;self.sample=sample
        return Output(output,True,'normal',self.integral,sample.source_ns)

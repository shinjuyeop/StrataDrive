"""Deterministic common inputs for speed-pi-equivalence-v1; no C++ calls."""
import math
import random
import sys

PERIOD = 20_000_000
MAX_AGE = 60_000_000
MAX_EPOCH = 2**32 - 1
MAX_INTEGER = 2**64 - 1
MAX_TARGET = 40 / 3.6
SEED = 32776


class Vectors:
    def __init__(self):
        self.lines = []

    def case(self, name, epoch=1):
        self.lines.append(f"new {name}")
        if epoch is not None:
            self.init(epoch)

    def init(self, epoch):
        self.lines.append(f"init {epoch}")

    def step(self, now, target=0., speed=0., *, epoch=1, sequence=0, source=None, permission=True):
        text = f"step {now} {float(target)!r} {int(permission)} {int(speed is not None)}"
        if speed is not None:
            text += f" {epoch} {sequence} {now if source is None else source} {float(speed)!r}"
        self.lines.append(text)


def generate(mil_rows, reference):
    v = Vectors()
    v.case("mil_87s_held_speed")
    for tick in range(4351):
        now = tick * PERIOD
        acquisition = now // 50_000_000
        v.step(now, reference(tick * .02), mil_rows[acquisition]["speed_mps"],
               sequence=acquisition, source=acquisition * 50_000_000)

    v.case("saturation_recovery")
    for tick in range(1500):
        target = MAX_TARGET if tick < 500 else 0 if tick < 1000 else 1
        speed = 0 if tick < 500 else 10 if tick < 1000 else 1
        v.step(tick * PERIOD, target, speed, sequence=tick)

    v.case("integral_accumulation_and_release")
    for tick in range(2400):
        speed = 0 if tick < 800 else 1.1 if tick < 1600 else 1
        v.step(tick * PERIOD, 1, speed, sequence=tick)

    v.case("uninitialized_and_new_init", epoch=None)
    v.init(0)
    v.step(0, math.nan, None, permission=False)
    v.step(PERIOD)
    v.init(1)
    v.step(2 * PERIOD, .02)
    v.init(1)
    v.init(0)
    v.step(3 * PERIOD, .02, sequence=1)
    v.step(4 * PERIOD, .02, sequence=2, permission=False)
    v.step(5 * PERIOD, .02, sequence=3)
    v.init(1)
    v.init(2)
    v.step(6 * PERIOD, .02, epoch=2)
    v.step(7 * PERIOD, .02, sequence=1, epoch=1)

    for delta in (-PERIOD, 0, PERIOD - 1, PERIOD, PERIOD + 1, 2 * PERIOD):
        v.case(f"period_delta_{delta}")
        v.step(100_000_000)
        v.step(100_000_000 + delta, sequence=1)
        v.step(100_000_000 + delta + PERIOD, sequence=2)

    for age in (-1, MAX_AGE - 1, MAX_AGE, MAX_AGE + 1):
        v.case(f"source_age_{age}")
        v.step(100_000_000, source=100_000_000 - age)

    v.case("cached_age_boundary")
    for tick in range(6):
        v.step(tick * PERIOD, 1, 1, source=0)

    speeds = [None, math.nan, math.inf, -math.inf, -1., -math.ulp(0.), -0.,
              math.ulp(0.), sys.float_info.max]
    for index, speed in enumerate(speeds):
        v.case(f"speed_value_{index}")
        v.step(0, speed=speed)
    targets = [math.nan, math.inf, -math.inf, -1., -math.ulp(0.), -0., math.ulp(0.),
               math.nextafter(MAX_TARGET, 0), MAX_TARGET, math.nextafter(MAX_TARGET, math.inf)]
    for index, target in enumerate(targets):
        v.case(f"target_value_{index}")
        v.step(0, target)

    for index, replacement in enumerate([
            dict(speed=.1, sequence=5, source=100_000_000),
            dict(sequence=5, source=100_000_001),
            dict(sequence=4, source=100_000_000),
            dict(sequence=6, source=100_000_000),
            dict(sequence=6, source=99_999_999),
            dict(epoch=0, sequence=6), dict(epoch=2, sequence=6),
            dict(sequence=6), dict(speed=-0., sequence=5, source=100_000_000)]):
        v.case(f"identity_{index}")
        v.step(100_000_000, sequence=5)
        v.step(120_000_000, **replacement)

    v.case("permission_before_other_input_faults")
    v.step(0, math.nan, None, permission=False)
    v.step(PERIOD, math.nan, None)
    v.case("period_before_permission")
    v.step(0)
    v.step(PERIOD + 1, math.nan, None, permission=False)
    v.case("target_before_speed")
    v.step(0, math.nan, None)
    v.case("speed_before_epoch")
    v.step(0, speed=math.nan, epoch=0)
    v.case("epoch_before_source")
    v.step(0, epoch=0, source=1)
    v.case("source_before_identity")
    v.step(0, sequence=1)
    v.step(PERIOD, sequence=0, source=PERIOD + 1)

    v.case("uint64_time_and_sequence_max", epoch=MAX_EPOCH)
    v.step(MAX_INTEGER - PERIOD, epoch=MAX_EPOCH, sequence=MAX_INTEGER - 1)
    v.step(MAX_INTEGER, epoch=MAX_EPOCH, sequence=MAX_INTEGER)
    v.step(PERIOD - 1, epoch=MAX_EPOCH)
    v.init(MAX_EPOCH)
    v.init(0)
    v.case("uint64_sequence_regression")
    v.step(0, sequence=MAX_INTEGER)
    v.step(PERIOD, sequence=0)

    # Adjacent binary64 inputs probe integration branches near output limits.
    for index, boundary in enumerate([0., .04, 2., 5.]):
        for side, error in enumerate([math.nextafter(boundary, -math.inf), boundary,
                                      math.nextafter(boundary, math.inf)]):
            v.case(f"positive_boundary_{index}_{side}")
            for tick in range(140):
                v.step(tick * PERIOD, error, 0., sequence=tick)
            v.case(f"negative_boundary_{index}_{side}")
            for tick in range(140):
                v.step(tick * PERIOD, 0., error, sequence=tick)

    v.case("preview_zero_crossing")
    for tick, (target, speed) in enumerate([(.0002, .0002), (0., .001), (0., 0.), (.0002, .0002)]):
        v.step(tick * PERIOD, target, speed, sequence=tick)

    rng = random.Random(SEED)
    v.case("seed32776_multirate")
    source = 0
    sequence = 0
    speed = 0.
    for tick in range(2000):
        now = tick * PERIOD
        current_source = now // 50_000_000 * 50_000_000
        target = min(MAX_TARGET, max(0., 4. + 3. * math.sin(tick / 150.)))
        if current_source != source or tick == 0:
            source = current_source
            sequence = source // 50_000_000
            speed = max(0., target + rng.uniform(-1.5, 1.5))
        v.step(now, target, speed, sequence=sequence, source=source)

    for case in range(20):
        v.case(f"seed32776_fault_reinit_{case}")
        for tick in range(30):
            now = 100_000_000 + tick * PERIOD
            if tick == 20:
                v.init(2)
            v.step(now, rng.uniform(0., MAX_TARGET), rng.uniform(0., 12.),
                   sequence=tick, epoch=1 if tick < 20 else 2, permission=tick != 10)
    return "\n".join(v.lines) + "\n"

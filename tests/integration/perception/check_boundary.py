#!/usr/bin/env python3
"""Independent mutation expectations for the Python -> C++ typed boundary."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from physical_ai.perception.contract import Detection, FrameIdentity, PerceptionResult
from physical_ai.perception.replay import frame_line, run_boundary


def main():
    result = PerceptionResult(
        FrameIdentity(1, 7, 1, 50_000_000),
        (Detection(2, 0.8, (1.0, 2.0, 30.0, 40.0)),),
        0,
        0,
        0,
    )
    baseline = frame_line(result, 50_000_000)
    mutations = {
        1: 150_000_000,
        2: 2,
        3: 2,
        4: 8,
        5: 0,
        6: 50_000_001,
        7: 150_000_001,
        8: 2,
        9: 2,
        10: 641,
        11: 385,
        12: 0,
        13: "0" * 64,
        15: 4,
        16: 0.34,
        17: -1,
        19: 641,
        20: 385,
    }
    rows = run_boundary(sys.argv[1], ["S 1 7 0", baseline, baseline, "P 150000000"])
    assert rows[0]["accepted"] and rows[1]["accepted"] and rows[1]["count"] == 1
    assert (
        not rows[2]["accepted"]
        and not rows[2]["available"]
        and not rows[3]["available"]
    )
    for column, value in mutations.items():
        changed = baseline.split()
        changed[column] = str(value)
        rows = run_boundary(sys.argv[1], ["S 1 7 0", " ".join(changed)])
        assert not rows[-1]["accepted"] and not rows[-1]["available"], (column, rows)
    print(
        json.dumps(
            {
                "status": "PASS",
                "mutations_rejected": len(mutations),
                "duplicate_rejected": True,
                "expired_unavailable": True,
            }
        )
    )


if __name__ == "__main__":
    main()

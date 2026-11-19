"""Collect the paired 2K person development experiment with the cooked renderer."""

import argparse
from pathlib import Path

from m10_collect_packaged_parking import collect
from m10_collect_occlusion_transfer import TESTS


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument(
        "--town", choices=("Town01_Opt", "Town02_Opt", "Town05_Opt"), required=True
    )
    p.add_argument("--port", type=int, default=2460)
    p.add_argument("--exclude-plan", type=Path)
    a = p.parse_args()
    collect(
        a.root / a.town,
        a.town,
        a.port,
        client_script=TESTS / "person_pair_capture.py",
        client_args=("--exclude-plan", a.exclude_plan.resolve())
        if a.exclude_plan
        else (),
    )

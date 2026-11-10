# Class calibration V1 audit serialization correction

The first audit failed at an in-memory equality check after all31,250 scorecards,
the direct calibration runs, numerical probes and Town04 regression had completed.
`dataclasses.asdict` retains tuple boxes in returned Python objects, while their
JSON artifacts contain array/list boxes. Comparing the newly returned fit tree
against the stored JSON tree therefore fails even when the serialized artifacts
are equal. Preserve the original source, freeze, selections, numeric report,
regression and failed `audit.log`; do not rerun selection with changed settings.

The supplemental `audit_class_calibration_v1.py` invokes the same frozen fit and
regression functions in temporary files and compares the **read-back JSON**
candidate trees exactly. No float tolerance, field deletion, score change,
threshold change or error removal is allowed. Only top-level creation times
remain outside candidate equality, as in the original audit. Bind the new audit
source/tests and this annex to an additional freeze before replay. Tests must
show tuple/list serialization equality and rejection of changed scores/counts.

The resulting audit still checks every scorecard, both chosen vectors, all810
selected raw predictions and their original strict primary scores. A fresh-source
archive subprocess must use the supplemental audit, preserve the first failure,
and report the same candidate results. This is an audit-path correction, not
new model quality evidence or a second calibration attempt.

"""One declared car-confidence revision on the validated960 raw outputs."""

from .class_calibration_v1 import decode as decode_vector

VECTOR = (0.6, 0.4, 0.6, 0.5, 0.5, 0.6)
CANDIDATE = "dfine-m-960-car-v1"


def decode(raw):
    return decode_vector(raw, VECTOR)

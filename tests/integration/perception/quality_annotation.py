"""Explicit v2 visible-mask policy: CARLA Pedestrians12 and Rider13 are person0.

V1 labels and frozen comparisons are immutable. This module is not used by the
v1 capture/scorer. A new prospective experiment must explicitly select v2.
"""

import numpy as np

SEMANTICS_BY_CLASS = {0: (12, 13), 1: (19,), 2: (14,), 3: (18,), 5: (16,), 7: (15,)}


def visible_boxes_v2(raw):
    if len(raw) != 640 * 384 * 4:
        raise ValueError("instance image layout")
    pixels = np.frombuffer(raw, np.uint8).reshape(384, 640, 4)
    tags = pixels[:, :, 2]
    ids = pixels[:, :, 1].astype(np.uint16) + (pixels[:, :, 0].astype(np.uint16) << 8)
    included, excluded = [], []
    for cls, semantic_tags in SEMANTICS_BY_CLASS.items():
        selected = np.isin(tags, semantic_tags)
        for ident in np.unique(ids[selected]):
            mask = selected & (ids == ident)
            y, x = np.where(mask)
            box = [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]
            row = dict(
                class_id=cls,
                instance_id=int(ident),
                visible_pixels=int(len(x)),
                box=box,
                semantic_tags=[int(t) for t in np.unique(tags[mask])],
            )
            if len(x) < 25 or box[2] - box[0] < 4 or box[3] - box[1] < 4:
                row["reason"] = "small_visible_support"
                excluded.append(row)
            else:
                included.append(row)
    return included, excluded

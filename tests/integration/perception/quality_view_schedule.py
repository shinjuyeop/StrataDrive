"""Evaluate selected original D-FINE views with their registered geometry and IDs."""

from quality_views import Views, base_from_raw, box_observations, obs, predict_proposals


class ScheduledViews(Views):
    def __init__(self, detector, indices):
        super().__init__(detector.model, detector.views.crops, "targeted")
        if not indices or indices[0] != 0 or list(indices) != sorted(set(indices)):
            raise ValueError("unique ordered views including the full frame")
        self.windows = []
        for i in indices:
            if not 0 <= i < len(obs.VIEWS):
                raise ValueError("unknown view")
            x, y, right, bottom, flip = obs.VIEWS[i]
            rect = tuple(
                round(v) for v in (x * 2560, y * 1536, right * 2560, bottom * 1536)
            )
            self.windows.append((i, rect, flip))

    def prepare(self, image):
        self.rgb = self.crops.frame(image)
        self.count = 0
        self.cars = []
        observations = []
        for index, rect, flip in self.windows:
            raw = self.forward(rect, flip)
            if index == 0:
                base = base_from_raw(image, self.model, raw, self.config, self.forward)
            other, cars = box_observations(raw, rect, flip, index)
            observations.extend(other)
            self.cars.extend(cars)
        new = predict_proposals(
            self.model.bundle,
            self.rgb,
            dict(base=base, obs=observations),
            self.classifiers,
        )
        return base, new, observations

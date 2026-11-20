"""Reuse identical D-FINE crop outputs within one source image."""

from quality_view_schedule import ScheduledViews


class CachedFrameViews(ScheduledViews):
    def prepare(self, image):
        self.outputs = {}
        return super().prepare(image)

    def forward(self, rect, flip=False):
        key = tuple(rect), bool(flip)
        if key not in self.outputs:
            self.outputs[key] = super().forward(rect, flip)
        return self.outputs[key]

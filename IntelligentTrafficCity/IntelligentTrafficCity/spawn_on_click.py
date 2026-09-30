# -*- coding: utf-8 -*-
"""
spawn_on_click.py
================================================================
Drop this file in the PROJECT ROOT folder (the same folder that
contains TrafficEngine_v2/ and SmartTrafficAI/), then run it INSTEAD
OF TrafficEngine_v2/main.py:

    python3 spawn_on_click.py

Everything else (AI, dashboard, keyboard controls: SPACE/A/R/Up/Down)
stays exactly the same - this file only adds ONE new feature:

    Left-click anywhere on the road canvas -> a car is placed right
    there, heading toward whichever of the 4 intersections is
    closest, in whichever direction makes sense from where you
    clicked. It then obeys normal traffic lights, following distance
    and the hard intersection lock like any other car.

It works by reusing TrafficEngine_v2/main.py's App class as-is (no
files are modified) and just adding a mouse binding on top of it.
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from TrafficEngine_v2.main import App  # noqa: E402
from TrafficEngine_v2.engine_core import Car, INTERSECTIONS  # noqa: E402


class ClickToSpawnApp(App):
    """Same app as TrafficEngine_v2/main.py, plus: left-click on the
    canvas places a car exactly where you clicked."""

    def __init__(self):
        super().__init__()
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    def on_canvas_click(self, event):
        x, y = event.x, event.y

        # Nearest intersection becomes this car's target.
        target = min(
            INTERSECTIONS,
            key=lambda t: (t[0] - x) ** 2 + (t[1] - y) ** 2,
        )
        tx, ty = target

        # Pick the direction that makes the car travel FROM the click
        # point TOWARD that intersection (same convention Car.spawn()
        # already uses: direction "N" means moving upward/toward a
        # target that is above the car, etc).
        dx = x - tx
        dy = y - ty

        if abs(dx) >= abs(dy):
            direction = "W" if dx > 0 else "E"
        else:
            direction = "N" if dy > 0 else "S"

        car = Car(self.canvas, direction, target)

        # Car.__init__ already spawned it far off-screen and drew the
        # rectangle there; move it to the actual click position now.
        car.x = float(x)
        car.y = float(y)
        car.draw()

        self.engine.cars.append(car)
        self.engine.total_spawned += 1


if __name__ == "__main__":
    ClickToSpawnApp().run()

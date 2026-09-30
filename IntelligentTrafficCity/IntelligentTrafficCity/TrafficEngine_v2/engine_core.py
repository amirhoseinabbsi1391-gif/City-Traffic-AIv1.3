# -*- coding: utf-8 -*-
"""
TrafficEngine_v2 - engine_core
================================================================
This module is the CORE simulation engine. It owns everything the
master spec calls "the body" of the system: road geometry, traffic
lights, vehicle physics (movement, following, the v3.3 hard
intersection lock), spawning, and the metrics that describe what is
actually happening in the city.

It is a refactor of TrafficEngine_v2/main.py (v3.3, "HARD
INTERSECTION LOCK"). The vehicle physics, hard-lock behaviour and
fixed-timing defaults are unchanged from the original file, so a
plain `TrafficEngine(canvas)` with `ai_enabled=False` behaves exactly
like the original engine ("BASELINE" mode / backward compatibility).

What's new here (all real, all driven by live simulation data):

- `Intersection.current_green_time` replaces the hard-coded
  GREEN_TIME check for the two green phases, so a green phase's
  duration can be set per-cycle instead of being a fixed constant.
- `TrafficEngine.ai_enabled` / `TrafficEngine.ai_controller` -
  when a controller (see SmartTrafficAI/ai_brain.py) is attached and
  enabled, the engine asks it to choose a green-time for every new
  green phase, based on the ACTUAL queue lengths measured from the
  live `self.cars` list. When disabled, it uses the original fixed
  GREEN_TIME - so BASELINE and AI runs use the identical code path,
  which is what makes a before/after comparison meaningful.
- A `NullCanvas` so the exact same engine code can run headless
  (no Tkinter, no display) for the benchmark/comparison script.
- Real, accumulated metrics (avg wait time, throughput, queue,
  congestion) computed from car state, not invented.
- A fail-safe: any exception raised by the AI controller is caught,
  the engine falls back to fixed timing for that decision, and
  `TrafficEngine.ai_status` reports the fallback so the UI can show
  it truthfully.
"""

import random

# ============================================================
# CONSTANTS  (unchanged from TrafficEngine_v2 v3.3)
# ============================================================

WIDTH = 1200
HEIGHT = 800

ROAD_W = 110
LANE_OFFSET = 27

CAR_W = 16
CAR_H = 10

CAR_SPEED = 2.2

FOLLOW_GAP = 34

INTERSECTION_HALF = 63     # visual / logical intersection square
HARD_LOCK_HALF = 82        # v3.3 hard-lock zone (slightly larger)

GREEN_TIME = 180           # BASELINE fixed green duration (ticks)
YELLOW_TIME = 35           # fixed yellow duration (ticks) - safety, never AI-controlled

MAX_CARS = 60
SPAWN_INTERVAL = 32

INTERSECTIONS = [
    (360, 250),
    (840, 250),
    (360, 550),
    (840, 550),
]

DIRECTIONS = ["N", "S", "E", "W"]

VECTOR = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}

# Discrete green-time choices the AI can pick between. NORMAL (index 1)
# equals the original fixed GREEN_TIME, so an untrained / neutral AI
# reproduces baseline behaviour exactly.
GREEN_OPTIONS = [60, 180, 360]  # kept in sync with SmartTrafficAI/ai_brain.py
GREEN_OPTION_NAMES = ["SHORT", "NORMAL", "LONG"]

# Distance (px) within which an approaching car counts toward a
# intersection's queue/demand for that approach group.
QUEUE_SENSE_DISTANCE = 200


# ============================================================
# HEADLESS CANVAS
# ============================================================

class NullCanvas:
    """
    A drop-in stand-in for a tkinter.Canvas that does nothing.
    Lets the exact same Car/Intersection/TrafficEngine code run
    without a display, so benchmark_compare.py can execute the real
    simulation (not a re-implementation of it) to gather honest
    baseline-vs-AI numbers.
    """

    def __init__(self):
        self._next_id = 1

    def _new_id(self):
        i = self._next_id
        self._next_id += 1
        return i

    def create_rectangle(self, *a, **k):
        return self._new_id()

    def create_line(self, *a, **k):
        return self._new_id()

    def create_oval(self, *a, **k):
        return self._new_id()

    def create_text(self, *a, **k):
        return self._new_id()

    def coords(self, *a, **k):
        pass

    def itemconfig(self, *a, **k):
        pass

    def delete(self, *a, **k):
        pass


# ============================================================
# INTERSECTION
# ============================================================

class Intersection:

    def __init__(self, x, y):
        self.x = x
        self.y = y

        # 0 = N/S green, 1 = N/S yellow, 2 = E/W green, 3 = E/W yellow
        self.phase = 0
        self.timer = 0

        # Adaptive green duration. Defaults to the fixed baseline
        # value; only changed by the engine's AI hook.
        self.current_green_time = GREEN_TIME

        # Explainability: last decision made for this intersection
        # (BASELINE or AI), refreshed every time a new green phase
        # starts. Used only for display - never fed back into logic.
        self.ai_decision_info = None

    def update(self):
        self.timer += 1

        if self.phase == 0:
            if self.timer >= self.current_green_time:
                self.phase = 1
                self.timer = 0

        elif self.phase == 1:
            if self.timer >= YELLOW_TIME:
                self.phase = 2
                self.timer = 0
                self.current_green_time = GREEN_TIME  # reset before next decision

        elif self.phase == 2:
            if self.timer >= self.current_green_time:
                self.phase = 3
                self.timer = 0

        elif self.phase == 3:
            if self.timer >= YELLOW_TIME:
                self.phase = 0
                self.timer = 0
                self.current_green_time = GREEN_TIME  # reset before next decision

    def light_for(self, approach):
        if approach in ("N", "S"):
            if self.phase == 0:
                return "green"
            if self.phase == 1:
                return "yellow"
            return "red"
        else:
            if self.phase == 2:
                return "green"
            if self.phase == 3:
                return "yellow"
            return "red"

    def phase_name(self):
        return {
            0: "N/S GREEN",
            1: "N/S YELLOW",
            2: "E/W GREEN",
            3: "E/W YELLOW",
        }[self.phase]

    def phase_type(self):
        """'NS' while phase in (0,1), 'EW' while phase in (2,3)."""
        return "NS" if self.phase in (0, 1) else "EW"

    def reset(self):
        self.phase = 0
        self.timer = 0
        self.current_green_time = GREEN_TIME
        self.ai_decision_info = None


# ============================================================
# CAR   (physics unchanged from TrafficEngine_v2 v3.3)
# ============================================================

class Car:

    def __init__(self, canvas, direction, target):
        self.canvas = canvas

        self.direction = direction
        self.target = target

        self.x = 0
        self.y = 0

        self.speed = CAR_SPEED
        self.waiting = False
        self.state = "APPROACHING"

        # v3.3 hard intersection lock
        self.intersection_locked = False
        self.passed = False

        # Real per-car metric: ticks spent waiting over its lifetime.
        # Used to compute genuine average-wait-time statistics.
        self.wait_ticks = 0

        self.color = random.choice([
            "#00d4ff", "#4ade80", "#facc15", "#fb7185",
            "#c084fc", "#fb923c", "#38bdf8", "#e879f9",
        ])

        self.spawn()

        self.id = self.canvas.create_rectangle(
            self.x - CAR_W / 2, self.y - CAR_H / 2,
            self.x + CAR_W / 2, self.y + CAR_H / 2,
            fill=self.color, outline="",
        )

    # ------------------------------------------------------------

    def spawn(self):
        tx, ty = self.target

        if self.direction == "N":
            self.x = tx + LANE_OFFSET
            self.y = HEIGHT + 50
        elif self.direction == "S":
            self.x = tx - LANE_OFFSET
            self.y = -50
        elif self.direction == "E":
            self.x = -50
            self.y = ty - LANE_OFFSET
        else:
            self.x = WIDTH + 50
            self.y = ty + LANE_OFFSET

    def approach(self):
        return {"N": "S", "S": "N", "E": "W", "W": "E"}[self.direction]

    def stop_line(self):
        tx, ty = self.target
        distance = INTERSECTION_HALF + 15

        if self.direction == "N":
            return "y", ty + distance
        if self.direction == "S":
            return "y", ty - distance
        if self.direction == "E":
            return "x", tx - distance
        return "x", tx + distance

    def inside_hard_zone(self):
        tx, ty = self.target
        return (
            tx - HARD_LOCK_HALF <= self.x <= tx + HARD_LOCK_HALF
            and ty - HARD_LOCK_HALF <= self.y <= ty + HARD_LOCK_HALF
        )

    def inside_intersection(self):
        tx, ty = self.target
        return (
            tx - INTERSECTION_HALF <= self.x <= tx + INTERSECTION_HALF
            and ty - INTERSECTION_HALF <= self.y <= ty + INTERSECTION_HALF
        )

    def has_crossed_stop_line(self):
        axis, line = self.stop_line()
        if axis == "y":
            if self.direction == "N":
                return self.y < line
            return self.y > line
        else:
            if self.direction == "E":
                return self.x > line
            return self.x < line

    def before_stop_line(self):
        axis, line = self.stop_line()
        if axis == "y":
            if self.direction == "N":
                return self.y >= line
            return self.y <= line
        else:
            if self.direction == "E":
                return self.x <= line
            return self.x >= line

    def would_cross_stop_line(self):
        axis, line = self.stop_line()
        dx, dy = VECTOR[self.direction]
        nx = self.x + dx * CAR_SPEED
        ny = self.y + dy * CAR_SPEED

        if axis == "y":
            if self.direction == "N":
                return self.y >= line and ny < line
            return self.y <= line and ny > line
        else:
            if self.direction == "E":
                return self.x <= line and nx > line
            return self.x >= line and nx < line

    def clamp_stop_line(self):
        axis, line = self.stop_line()
        if axis == "y":
            self.y = line
        else:
            self.x = line

    def move(self):
        dx, dy = VECTOR[self.direction]
        self.x += dx * CAR_SPEED
        self.y += dy * CAR_SPEED

    def approaching_distance(self):
        """Distance (px) from the car to its target intersection,
        measured along its direction of travel. Used for AI queue
        sensing - counts cars that are approaching, not only ones
        already stopped at the line."""
        tx, ty = self.target
        if self.direction in ("N", "S"):
            return abs(self.y - ty)
        return abs(self.x - tx)

    def blocked_by_car(self, cars):
        if self.intersection_locked:
            return False

        for other in cars:
            if other is self:
                continue
            if other.direction != self.direction:
                continue
            if other.target != self.target:
                continue
            if other.intersection_locked:
                continue

            dx = other.x - self.x
            dy = other.y - self.y

            if self.direction == "N":
                if dy < 0 and abs(dx) < 20 and abs(dy) < FOLLOW_GAP:
                    return True
            elif self.direction == "S":
                if dy > 0 and abs(dx) < 20 and abs(dy) < FOLLOW_GAP:
                    return True
            elif self.direction == "E":
                if dx > 0 and abs(dy) < 20 and abs(dx) < FOLLOW_GAP:
                    return True
            elif self.direction == "W":
                if dx < 0 and abs(dy) < 20 and abs(dx) < FOLLOW_GAP:
                    return True

        return False

    def lock_intersection(self, engine):
        if self.intersection_locked:
            return
        self.intersection_locked = True
        self.state = "CROSSING"
        self.waiting = False
        self.speed = CAR_SPEED

        if not self.passed:
            self.passed = True
            engine.total_passed += 1

    def unlock_intersection(self):
        if not self.intersection_locked:
            return
        if not self.inside_hard_zone():
            self.intersection_locked = False
            self.state = "EXITED"

    def enforce_hard_lock(self, engine):
        if self.inside_hard_zone():
            self.lock_intersection(engine)
            self.speed = CAR_SPEED
            self.waiting = False
            self.move()
            self.unlock_intersection()
            self.draw()
            return True
        return False

    def update(self, engine):
        self.waiting = False

        if self.enforce_hard_lock(engine):
            return

        if self.intersection_locked:
            self.speed = CAR_SPEED
            self.waiting = False
            self.move()
            self.unlock_intersection()
            self.draw()
            return

        intersection = engine.intersection_map[self.target]

        if self.before_stop_line():
            light = intersection.light_for(self.approach())

            if light != "green":
                if self.would_cross_stop_line():
                    self.clamp_stop_line()
                self.speed = 0
                self.waiting = True
                self.state = "WAITING"
                self.draw()
                return

            if self.blocked_by_car(engine.cars):
                self.speed = 0
                self.waiting = True
                self.state = "WAITING"
                self.draw()
                return

            self.speed = CAR_SPEED
            self.move()

            if self.has_crossed_stop_line():
                self.lock_intersection(engine)

            self.draw()
            return

        if self.state == "WAITING":
            light = intersection.light_for(self.approach())

            if light != "green":
                self.speed = 0
                self.waiting = True
                self.clamp_stop_line()
                self.draw()
                return

            if self.blocked_by_car(engine.cars):
                self.speed = 0
                self.waiting = True
                self.draw()
                return

            self.speed = CAR_SPEED
            self.move()

            if self.has_crossed_stop_line():
                self.lock_intersection(engine)

            self.draw()
            return

        if self.state == "EXITED":
            if self.blocked_by_car(engine.cars):
                self.speed = 0
                self.waiting = True
            else:
                self.speed = CAR_SPEED
                self.move()
            self.draw()
            return

        self.speed = CAR_SPEED
        self.move()
        self.draw()

    def draw(self):
        self.canvas.coords(
            self.id,
            self.x - CAR_W / 2, self.y - CAR_H / 2,
            self.x + CAR_W / 2, self.y + CAR_H / 2,
        )

    def outside(self):
        return (
            self.x < -100 or self.x > WIDTH + 100
            or self.y < -100 or self.y > HEIGHT + 100
        )


# ============================================================
# TRAFFIC ENGINE
# ============================================================

class TrafficEngine:
    """
    The core simulation. Owns the road network, lights, cars,
    spawning, rendering calls, and (new) the AI interface:

        get_traffic_state(idx)   -> state tuple for one intersection
        apply/consult ai_controller at every new green phase
        get_metrics()            -> real, live comparison metrics

    `ai_controller` is injected from the outside (see main.py /
    benchmark_compare.py) so this module has no hard dependency on
    SmartTrafficAI - if the AI package is missing entirely, the
    engine still runs exactly as TrafficEngine_v2 always did.
    """

    def __init__(self, canvas=None, ai_controller=None, ai_enabled=False):
        self.canvas = canvas if canvas is not None else NullCanvas()

        self.intersections = [Intersection(x, y) for x, y in INTERSECTIONS]
        self.intersection_map = {
            pos: self.intersections[i] for i, pos in enumerate(INTERSECTIONS)
        }

        self.cars = []
        self.total_spawned = 0
        self.total_passed = 0

        self.spawn_timer = 0
        self.running = True

        # ---- AI interface state ----
        self.ai_controller = ai_controller
        self.ai_enabled = bool(ai_enabled and ai_controller is not None)
        self.ai_status = "ON" if self.ai_enabled else "OFF"
        self.last_decision = {}          # (intersection_idx, phase_type) -> (state, action_index)
        self.ai_decisions_log = []       # rolling list of recent decisions, for the dashboard

        # ---- Real, accumulated metrics ----
        self.completed_wait_sum = 0      # sum of wait_ticks for cars that finished their trip
        self.completed_count = 0
        self.tick_count = 0

        self.create_city()

        # Make the very first green phase of every intersection go
        # through the same decision path as every later one.
        for idx, intersection in enumerate(self.intersections):
            self._on_new_green_phase(idx, intersection)

    # ========================================================
    # CITY / RENDERING  (unchanged geometry from v3.3)
    # ========================================================

    def create_city(self):
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#07111f", outline="")

        for x in range(0, WIDTH, 40):
            self.canvas.create_line(x, 0, x, HEIGHT, fill="#0b1728")
        for y in range(0, HEIGHT, 40):
            self.canvas.create_line(0, y, WIDTH, y, fill="#0b1728")

        for x, y in INTERSECTIONS:
            self.canvas.create_rectangle(x - ROAD_W / 2, 0, x + ROAD_W / 2, HEIGHT, fill="#182535", outline="")
            self.canvas.create_rectangle(0, y - ROAD_W / 2, WIDTH, y + ROAD_W / 2, fill="#182535", outline="")

        for x, y in INTERSECTIONS:
            self.canvas.create_line(x, 0, x, HEIGHT, fill="#334155", dash=(14, 14))
            self.canvas.create_line(0, y, WIDTH, y, fill="#334155", dash=(14, 14))

        for x, y in INTERSECTIONS:
            self.canvas.create_rectangle(
                x - INTERSECTION_HALF, y - INTERSECTION_HALF,
                x + INTERSECTION_HALF, y + INTERSECTION_HALF,
                fill="#202d3d", outline="#475569", width=2,
            )

        self.draw_stop_lines()
        self.create_traffic_lights()

    def draw_stop_lines(self):
        for x, y in INTERSECTIONS:
            self.canvas.create_line(x - 42, y - 78, x + 42, y - 78, fill="#f8fafc", width=4)
            self.canvas.create_line(x - 42, y + 78, x + 42, y + 78, fill="#f8fafc", width=4)
            self.canvas.create_line(x - 78, y - 42, x - 78, y + 42, fill="#f8fafc", width=4)
            self.canvas.create_line(x + 78, y - 42, x + 78, y + 42, fill="#f8fafc", width=4)

    def create_traffic_lights(self):
        self.light_objects = []

        for intersection in self.intersections:
            x, y = intersection.x, intersection.y

            positions = {
                "N": (x + 48, y - 91),
                "S": (x - 48, y + 91),
                "E": (x + 91, y + 48),
                "W": (x - 91, y - 48),
            }

            for approach, (lx, ly) in positions.items():
                if approach in ("N", "S"):
                    self.canvas.create_rectangle(lx - 10, ly - 25, lx + 10, ly + 25, fill="#050b14", outline="#64748b")
                else:
                    self.canvas.create_rectangle(lx - 25, ly - 10, lx + 25, ly + 10, fill="#050b14", outline="#64748b")

                lights = []
                for i in range(3):
                    if approach in ("N", "S"):
                        cy = ly - 15 + i * 15
                        lamp = self.canvas.create_oval(lx - 6, cy - 6, lx + 6, cy + 6, fill="#17202b", outline="#475569")
                    else:
                        cx = lx - 15 + i * 15
                        lamp = self.canvas.create_oval(cx - 6, ly - 6, cx + 6, ly + 6, fill="#17202b", outline="#475569")
                    lights.append(lamp)

                self.light_objects.append({
                    "intersection": intersection,
                    "approach": approach,
                    "lights": lights,
                })

        self.update_traffic_lights()

    def update_traffic_lights(self):
        for obj in self.light_objects:
            intersection = obj["intersection"]
            approach = obj["approach"]
            state = intersection.light_for(approach)
            lights = obj["lights"]

            self.canvas.itemconfig(lights[0], fill="#450a0a")
            self.canvas.itemconfig(lights[1], fill="#453800")
            self.canvas.itemconfig(lights[2], fill="#052e16")

            if state == "red":
                self.canvas.itemconfig(lights[0], fill="#ef4444")
            elif state == "yellow":
                self.canvas.itemconfig(lights[1], fill="#facc15")
            else:
                self.canvas.itemconfig(lights[2], fill="#22c55e")

    # ========================================================
    # AI INTERFACE
    # ========================================================

    def queue_for_group(self, intersection, group):
        """Real demand measurement: counts cars heading for this
        intersection, in this approach group ('NS' or 'EW'), that are
        within QUEUE_SENSE_DISTANCE of the stop line."""
        approaches = ("N", "S") if group == "NS" else ("E", "W")
        pos = (intersection.x, intersection.y)
        count = 0
        for car in self.cars:
            if car.target != pos:
                continue
            if car.approach() not in approaches:
                continue
            if car.intersection_locked:
                continue
            if car.approaching_distance() <= QUEUE_SENSE_DISTANCE:
                count += 1
        return count

    def get_traffic_state(self, idx):
        """Public AI interface: real traffic state for intersection idx."""
        intersection = self.intersections[idx]
        phase_type = intersection.phase_type()
        opposite_type = "EW" if phase_type == "NS" else "NS"

        q_this = self.queue_for_group(intersection, phase_type)
        q_opp = self.queue_for_group(intersection, opposite_type)

        bucket_this = min(q_this, 8) // 2
        bucket_opp = min(q_opp, 8) // 2

        return {
            "intersection": idx,
            "phase_type": phase_type,
            "queue_this": q_this,
            "queue_opposite": q_opp,
            "state_tuple": (bucket_this, bucket_opp),
        }

    def _on_new_green_phase(self, idx, intersection):
        """Called whenever a green phase (NS or EW) begins at
        `intersection`. Learns from the outcome of the previous
        decision for this same (intersection, phase-type), then
        chooses (or falls back to) a green duration for the phase
        that just started."""

        info = self.get_traffic_state(idx)
        phase_type = info["phase_type"]
        state = info["state_tuple"]
        q_this = info["queue_this"]
        q_opp = info["queue_opposite"]
        key = (idx, phase_type)

        # Real reward: negative total congestion pressure at this
        # intersection right now. Never invented.
        reward = -(q_this + q_opp)

        if self.ai_enabled and self.ai_controller is not None:
            try:
                if key in self.last_decision:
                    prev_state, prev_action = self.last_decision[key]
                    self.ai_controller.learn(prev_state, prev_action, reward, state)

                green_time, decision_info = self.ai_controller.decide(
                    state, phase_type, q_this, q_opp
                )

                intersection.current_green_time = green_time
                intersection.ai_decision_info = decision_info
                self.last_decision[key] = (state, decision_info["action_index"])
                self.ai_status = "ON"

                self.ai_decisions_log.append(dict(decision_info, intersection=idx))
                if len(self.ai_decisions_log) > 50:
                    self.ai_decisions_log.pop(0)

            except Exception as exc:  # AI fail-safe - never crash the engine
                self.ai_status = "FALLBACK ({0})".format(type(exc).__name__)
                intersection.current_green_time = GREEN_TIME
                intersection.ai_decision_info = {
                    "mode": "FALLBACK",
                    "phase": phase_type,
                    "green_time": GREEN_TIME,
                    "reason": "AI error caught, using fixed timing: {0}".format(exc),
                    "confidence": 0.0,
                }
        else:
            intersection.current_green_time = GREEN_TIME
            intersection.ai_decision_info = {
                "mode": "BASELINE",
                "phase": phase_type,
                "green_time": GREEN_TIME,
                "queue_this": q_this,
                "queue_opposite": q_opp,
                "reason": "Fixed timing (AI disabled)",
                "confidence": 0.0,
            }
            self.ai_status = "OFF"

    def set_ai_enabled(self, enabled):
        self.ai_enabled = bool(enabled and self.ai_controller is not None)
        self.ai_status = "ON" if self.ai_enabled else "OFF"

        # Re-decide immediately for whichever intersections are
        # currently mid-green, instead of waiting for their next
        # phase to start. Without this, toggling AI only takes effect
        # up to a full green+yellow cycle later (a few seconds), which
        # makes the switch look like it "did nothing". This only ever
        # changes how long the CURRENT green lasts (shrinks or grows
        # it) - the mandatory yellow phase before red is never
        # skipped, so it stays safe for any car already stopped or
        # crossing.
        for idx, intersection in enumerate(self.intersections):
            if intersection.phase in (0, 2):
                self._on_new_green_phase(idx, intersection)

    # ========================================================
    # SPAWN
    # ========================================================

    def spawn_car(self):
        target = random.choice(INTERSECTIONS)
        direction = random.choice(DIRECTIONS)

        car = Car(self.canvas, direction, target)

        for other in self.cars:
            if abs(other.x - car.x) < 35 and abs(other.y - car.y) < 35:
                self.canvas.delete(car.id)
                return

        self.cars.append(car)
        self.total_spawned += 1

    # ========================================================
    # MAIN UPDATE
    # ========================================================

    def update(self):
        if not self.running:
            return

        self.tick_count += 1

        for idx, intersection in enumerate(self.intersections):
            prev_phase = intersection.phase
            intersection.update()

            just_started_green = (
                intersection.phase != prev_phase
                and intersection.phase in (0, 2)
                and intersection.timer == 0
            )
            if just_started_green:
                self._on_new_green_phase(idx, intersection)

        self.spawn_timer += 1
        if self.spawn_timer >= SPAWN_INTERVAL:
            self.spawn_timer = 0
            if len(self.cars) < MAX_CARS:
                self.spawn_car()

        for car in list(self.cars):
            car.update(self)

            if car.waiting:
                car.wait_ticks += 1

            if car.outside():
                self.completed_wait_sum += car.wait_ticks
                self.completed_count += 1
                self.canvas.delete(car.id)
                if car in self.cars:
                    self.cars.remove(car)

        self.update_traffic_lights()

        if hasattr(self, "monitor_callback"):
            waiting = sum(1 for car in self.cars if car.waiting)
            locked = sum(1 for car in self.cars if car.intersection_locked)
            self.monitor_callback(len(self.cars), self.total_spawned, self.total_passed, waiting, locked)

    def get_metrics(self):
        """Real, live metrics - the single source of truth used by
        both the dashboard and the baseline-vs-AI comparison tool."""
        active = len(self.cars)
        waiting_now = sum(1 for c in self.cars if c.waiting)

        avg_wait_ticks = (
            self.completed_wait_sum / self.completed_count
            if self.completed_count > 0 else 0.0
        )

        return {
            "ticks": self.tick_count,
            "cars_active": active,
            "total_spawned": self.total_spawned,
            "total_passed": self.total_passed,
            "completed_trips": self.completed_count,
            "queue_length": waiting_now,
            "congestion": (waiting_now / active) if active > 0 else 0.0,
            "avg_wait_ticks": avg_wait_ticks,
            "avg_wait_seconds": avg_wait_ticks / 60.0,  # engine runs ~60 ticks/sec
            "ai_status": self.ai_status,
        }

    # ========================================================

    def reset(self):
        for car in self.cars:
            self.canvas.delete(car.id)
        self.cars.clear()

        self.total_spawned = 0
        self.total_passed = 0
        self.spawn_timer = 0

        self.completed_wait_sum = 0
        self.completed_count = 0
        self.tick_count = 0

        self.last_decision.clear()
        self.ai_decisions_log.clear()

        for intersection in self.intersections:
            intersection.reset()

        for idx, intersection in enumerate(self.intersections):
            self._on_new_green_phase(idx, intersection)

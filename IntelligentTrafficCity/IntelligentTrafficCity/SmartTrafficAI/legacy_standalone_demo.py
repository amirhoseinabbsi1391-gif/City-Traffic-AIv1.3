import tkinter as tk
import random
import math
import json
import os
from collections import defaultdict, deque

# ============================================================
# SmartTrafficAI v2.6
# ============================================================
# 4 Intersections - 2x2
# Two-way roads
# Separate lanes
# 4 independent traffic lights / intersection
# Real stop lines
# Q-Learning
# Python + Tkinter only
# ============================================================

WIDTH = 1200
HEIGHT = 760

ROAD = 110
LANE = 27

INTERSECTION_SIZE = 110

CAR_SPEED = 2.5
MAX_CARS = 110

FRAME_MS = 35

GREEN_TIME = 110
YELLOW_TIME = 24

SPAWN_INTERVAL = 10

QTABLE_FILE = "traffic_qtable.json"

DIRS = ["N", "E", "S", "W"]

VEC = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0)
}


def opposite(d):
    return {
        "N": "S",
        "S": "N",
        "E": "W",
        "W": "E"
    }[d]


# ============================================================
# 4 INTERSECTIONS
# ============================================================

INTERSECTIONS = {
    0: (360, 250),
    1: (840, 250),
    2: (360, 550),
    3: (840, 550)
}

GRAPH = {
    0: [1, 2],
    1: [0, 3],
    2: [0, 3],
    3: [1, 2]
}


# ============================================================
# Q LEARNING
# ============================================================

class QLearning:

    def __init__(self):

        self.q = defaultdict(
            lambda: [0.0, 0.0, 0.0]
        )

        self.alpha = 0.14
        self.gamma = 0.92

        self.epsilon = 0.25

        self.load()

    def key(self, state):
        return "|".join(map(str, state))

    def choose(self, state):

        key = self.key(state)

        if random.random() < self.epsilon:
            return random.randint(0, 2)

        values = self.q[key]

        return max(
            range(3),
            key=lambda i: values[i]
        )

    def learn(
        self,
        old_state,
        action,
        reward,
        new_state
    ):

        old_key = self.key(old_state)
        new_key = self.key(new_state)

        old_value = self.q[old_key][action]
        future = max(self.q[new_key])

        self.q[old_key][action] += (
            self.alpha *
            (
                reward
                + self.gamma * future
                - old_value
            )
        )

    def save(self):

        try:
            with open(
                QTABLE_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    dict(self.q),
                    f
                )

        except Exception:
            pass

    def load(self):

        if not os.path.exists(QTABLE_FILE):
            return

        try:

            with open(
                QTABLE_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            for k, v in data.items():
                self.q[k] = v

        except Exception:
            pass


# ============================================================
# TRAFFIC LIGHT
# ============================================================

class TrafficLight:

    def __init__(self, sim, node):

        self.sim = sim
        self.node = node

        # NS or EW
        self.phase = "NS"

        # GREEN / YELLOW
        self.state = "GREEN"

        self.timer = GREEN_TIME

        self.next_phase = None

    def allows(self, approach):

        if self.state != "GREEN":
            return False

        if self.phase == "NS":
            return approach in ("N", "S")

        return approach in ("E", "W")

    def request(self, phase):

        if phase == self.phase:
            return

        if self.state == "GREEN":

            self.state = "YELLOW"

            self.timer = YELLOW_TIME

            self.next_phase = phase

    def update(self):

        self.timer -= 1

        if self.timer > 0:
            return

        # -----------------------------
        # Yellow -> new green
        # -----------------------------

        if self.state == "YELLOW":

            self.phase = self.next_phase
            self.next_phase = None

            self.state = "GREEN"

            self.timer = GREEN_TIME

            return

        # -----------------------------
        # Green cycle finished
        # -----------------------------

        if self.sim.ai_enabled:

            state = self.sim.get_state(
                self.node
            )

            action = self.sim.ai.choose(
                state
            )

            if action == 0:
                desired = self.phase

            elif action == 1:
                desired = "NS"

            else:
                desired = "EW"

            if desired != self.phase:

                self.request(desired)

            else:

                self.timer = GREEN_TIME

        else:

            # Fixed controller
            desired = (
                "EW"
                if self.phase == "NS"
                else "NS"
            )

            self.request(desired)


# ============================================================
# ROAD / LANE GEOMETRY
# ============================================================

def lane_offset(direction):

    # Each direction gets its own lane.
    #
    # Northbound:
    # right side of road
    #
    # Southbound:
    # opposite side
    #
    if direction == "N":
        return LANE / 2

    if direction == "S":
        return -LANE / 2

    if direction == "E":
        return -LANE / 2

    return LANE / 2


def lane_position_for_segment(
    start,
    target,
    distance_from_start
):

    sx, sy = INTERSECTIONS[start]
    tx, ty = INTERSECTIONS[target]

    dx = tx - sx
    dy = ty - sy

    if abs(dx) > abs(dy):

        direction = "E" if dx > 0 else "W"

    else:

        direction = "S" if dy > 0 else "N"

    offset = lane_offset(direction)

    if direction in ("E", "W"):

        x = sx + (
            distance_from_start
            if direction == "E"
            else -distance_from_start
        )

        y = sy + offset

    else:

        x = sx + offset

        y = sy + (
            distance_from_start
            if direction == "S"
            else -distance_from_start
        )

    return x, y


# ============================================================
# CAR
# ============================================================

class Car:

    def __init__(self, sim):

        self.sim = sim

        self.route = self.make_route()

        self.segment = 0

        self.finished = False

        self.wait = 0

        self.total = 0

        self.body = None

        self.distance = -160

        self.spawn()

    # --------------------------------------------------------

    def make_route(self):

        start = random.choice(
            list(INTERSECTIONS.keys())
        )

        destination = random.choice(
            [
                n
                for n in INTERSECTIONS
                if n != start
            ]
        )

        q = deque(
            [(start, [start])]
        )

        visited = {start}

        while q:

            node, path = q.popleft()

            if node == destination:
                return path

            for nxt in GRAPH[node]:

                if nxt not in visited:

                    visited.add(nxt)

                    q.append(
                        (
                            nxt,
                            path + [nxt]
                        )
                    )

        return [start, destination]

    # --------------------------------------------------------

    def segment_direction(self):

        if self.segment >= len(self.route) - 1:
            return None

        a = self.route[self.segment]
        b = self.route[self.segment + 1]

        ax, ay = INTERSECTIONS[a]
        bx, by = INTERSECTIONS[b]

        if abs(bx - ax) > abs(by - ay):

            return "E" if bx > ax else "W"

        return "S" if by > ay else "N"

    # --------------------------------------------------------

    def spawn(self):

        direction = self.segment_direction()

        if direction is None:
            return

        start = self.route[0]

        sx, sy = INTERSECTIONS[start]

        offset = lane_offset(direction)

        spawn_distance = 165

        if direction == "E":

            self.x = sx - spawn_distance
            self.y = sy + offset

        elif direction == "W":

            self.x = sx + spawn_distance
            self.y = sy + offset

        elif direction == "S":

            self.x = sx + offset
            self.y = sy - spawn_distance

        else:

            self.x = sx + offset
            self.y = sy + spawn_distance

    # --------------------------------------------------------

    def target_node(self):

        if self.segment >= len(self.route) - 1:
            return None

        return self.route[
            self.segment + 1
        ]

    # --------------------------------------------------------

    def direction(self):

        return self.segment_direction()

    # --------------------------------------------------------

    def target_distance(self):

        target = self.target_node()

        if target is None:
            return 99999

        tx, ty = INTERSECTIONS[target]

        d = self.direction()

        if d == "E":
            return tx - self.x

        if d == "W":
            return self.x - tx

        if d == "S":
            return ty - self.y

        return self.y - ty

    # --------------------------------------------------------

    def inside_intersection(self):

        target = self.target_node()

        if target is None:
            return False

        tx, ty = INTERSECTIONS[target]

        return (
            abs(self.x - tx) <= 55
            and
            abs(self.y - ty) <= 55
        )

    # --------------------------------------------------------

    def stop_line_distance(self):

        # Stop before the intersection.
        #
        # Road half = 55
        # car must stop outside intersection.
        return 72

    # --------------------------------------------------------

    def at_red_light(self):

        target = self.target_node()

        if target is None:
            return False

        # Once inside:
        # NEVER stop for red.
        if self.inside_intersection():
            return False

        distance = self.target_distance()

        if distance > self.stop_line_distance():
            return False

        direction = self.direction()

        if direction is None:
            return True

        # Direction of entrance is opposite
        # to travel direction.
        approach = opposite(direction)

        light = self.sim.lights[target]

        return not light.allows(
            approach
        )

    # --------------------------------------------------------

    def car_ahead(self):

        direction = self.direction()

        if direction is None:
            return None

        vx, vy = VEC[direction]

        nearest = None
        nearest_distance = 99999

        for other in self.sim.cars:

            if other is self:
                continue

            if other.finished:
                continue

            if other.direction() != direction:
                continue

            dx = other.x - self.x
            dy = other.y - self.y

            forward = (
                dx * vx +
                dy * vy
            )

            if forward <= 0:
                continue

            lateral = abs(
                dx * vy -
                dy * vx
            )

            if lateral > 22:
                continue

            if forward < nearest_distance:

                nearest_distance = forward
                nearest = other

        if nearest is not None:

            return nearest_distance

        return None

    # --------------------------------------------------------

    def should_stop(self):

        # Red/yellow
        if self.at_red_light():
            return True

        # Car following
        gap = self.car_ahead()

        if gap is not None:

            if gap < 32:
                return True

        return False

    # --------------------------------------------------------

    def update(self):

        if self.finished:
            return

        self.total += 1

        if self.should_stop():

            self.wait += 1

            return

        direction = self.direction()

        if direction is None:
            return

        vx, vy = VEC[direction]

        self.x += vx * CAR_SPEED
        self.y += vy * CAR_SPEED

        # ----------------------------------
        # Reached target
        # ----------------------------------

        target = self.target_node()

        if target is None:
            return

        tx, ty = INTERSECTIONS[target]

        distance = math.hypot(
            self.x - tx,
            self.y - ty
        )

        if distance < 4:

            self.x = tx
            self.y = ty

            self.segment += 1

            # Continue to next segment
            if self.segment < len(self.route) - 1:

                # Recalculate lane for new direction
                next_direction = (
                    self.segment_direction()
                )

                if next_direction:

                    offset = lane_offset(
                        next_direction
                    )

                    if next_direction in ("E", "W"):

                        self.y = ty + offset

                    else:

                        self.x = tx + offset

            else:

                self.finished = True

                self.sim.completed += 1

    # --------------------------------------------------------

    def draw(self):

        if self.body is None:

            self.body = (
                self.sim.canvas.create_rectangle(
                    0,
                    0,
                    0,
                    0,
                    fill="#42a5f5",
                    outline="",
                    tags="cars"
                )
            )

        direction = self.direction()

        if direction in ("N", "S"):

            x1 = self.x - 5
            y1 = self.y - 11
            x2 = self.x + 5
            y2 = self.y + 11

        else:

            x1 = self.x - 11
            y1 = self.y - 5
            x2 = self.x + 11
            y2 = self.y + 5

        self.sim.canvas.coords(
            self.body,
            x1,
            y1,
            x2,
            y2
        )


# ============================================================
# SIMULATION
# ============================================================

class Simulation:

    def __init__(self, root):

        self.root = root

        self.canvas = tk.Canvas(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg="#10141c",
            highlightthickness=0
        )

        self.canvas.pack(
            side="left"
        )

        self.panel = tk.Frame(
            root,
            width=260,
            bg="#171c26"
        )

        self.panel.pack(
            side="right",
            fill="y"
        )

        self.ai_enabled = True

        self.cars = []

        self.completed = 0
        self.spawned = 0

        self.tick = 0

        self.speed = 1

        self.ai = QLearning()

        self.lights = {
            node:
            TrafficLight(
                self,
                node
            )
            for node in INTERSECTIONS
        }

        self.last_states = {}
        self.last_actions = {}

        self.build_city()
        self.build_ui()

        root.bind(
            "<space>",
            lambda e:
            self.toggle_ai()
        )

        root.bind(
            "<Up>",
            lambda e:
            self.change_speed(1)
        )

        root.bind(
            "<Down>",
            lambda e:
            self.change_speed(-1)
        )

        root.bind(
            "r",
            lambda e:
            self.reset()
        )

        root.bind(
            "c",
            lambda e:
            self.clear_qtable()
        )

        self.loop()

    # ========================================================
    # CITY DRAWING
    # ========================================================

    def build_city(self):

        self.canvas.delete("city")

        # Vertical roads
        for x in [360, 840]:

            self.canvas.create_rectangle(
                x - 55,
                0,
                x + 55,
                HEIGHT,
                fill="#292f39",
                outline="",
                tags="city"
            )

            # Center divider
            self.canvas.create_line(
                x,
                0,
                x,
                HEIGHT,
                fill="#555b66",
                dash=(18, 18),
                tags="city"
            )

        # Horizontal roads
        for y in [250, 550]:

            self.canvas.create_rectangle(
                0,
                y - 55,
                WIDTH,
                y + 55,
                fill="#292f39",
                outline="",
                tags="city"
            )

            # Center divider
            self.canvas.create_line(
                0,
                y,
                WIDTH,
                y,
                fill="#555b66",
                dash=(18, 18),
                tags="city"
            )

        # Intersections
        for x, y in INTERSECTIONS.values():

            self.canvas.create_rectangle(
                x - 55,
                y - 55,
                x + 55,
                y + 55,
                fill="#353c47",
                outline="#5c6573",
                width=2,
                tags="city"
            )

        self.draw_lights()

    # ========================================================

    def light_position(
        self,
        x,
        y,
        direction
    ):

        offset = 68

        if direction == "N":
            return x - 18, y - offset

        if direction == "S":
            return x + 18, y + offset

        if direction == "E":
            return x + offset, y - 18

        return x - offset, y + 18

    # ========================================================

    def draw_lights(self):

        self.canvas.delete(
            "lights"
        )

        for node in INTERSECTIONS:

            x, y = INTERSECTIONS[node]

            light = self.lights[node]

            for direction in DIRS:

                lx, ly = self.light_position(
                    x,
                    y,
                    direction
                )

                if light.state == "YELLOW":

                    color = "#ffd60a"

                elif light.allows(
                    direction
                ):

                    color = "#30d158"

                else:

                    color = "#ff3b30"

                r = 8

                self.canvas.create_oval(
                    lx-r,
                    ly-r,
                    lx+r,
                    ly+r,
                    fill=color,
                    outline="#111",
                    width=2,
                    tags="lights"
                )

                self.canvas.create_text(
                    lx,
                    ly-14,
                    text=direction,
                    fill="#d0d5dd",
                    font=("Arial", 7),
                    tags="lights"
                )

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        tk.Label(
            self.panel,
            text="SmartTrafficAI",
            bg="#171c26",
            fg="white",
            font=("Arial", 18, "bold")
        ).pack(
            pady=(20, 5)
        )

        tk.Label(
            self.panel,
            text="Q-Learning Traffic Control",
            bg="#171c26",
            fg="#9ba4b5",
            font=("Arial", 9)
        ).pack(
            pady=(0, 20)
        )

        self.ai_label = tk.Label(
            self.panel,
            text="AI: ON",
            bg="#171c26",
            fg="#30d158",
            font=("Arial", 13, "bold")
        )

        self.ai_label.pack(
            pady=8
        )

        self.stats = tk.Label(
            self.panel,
            text="",
            justify="left",
            anchor="w",
            bg="#171c26",
            fg="#d9dee8",
            font=("Consolas", 10)
        )

        self.stats.pack(
            padx=15,
            pady=20,
            fill="x"
        )

        tk.Label(
            self.panel,
            text=
            "SPACE  AI ON/OFF\n"
            "↑ ↓    Speed\n"
            "R      Reset cars\n"
            "C      Clear Q-table",
            justify="left",
            bg="#171c26",
            fg="#9ba4b5",
            font=("Consolas", 9)
        ).pack(
            padx=15,
            pady=20
        )

    # ========================================================
    # AI STATE
    # ========================================================

    def queue_counts(self, node):

        result = {
            "N": 0,
            "E": 0,
            "S": 0,
            "W": 0
        }

        for car in self.cars:

            if car.finished:
                continue

            if car.target_node() != node:
                continue

            if car.inside_intersection():
                continue

            d = car.target_distance()

            if d < 150:

                direction = car.direction()

                if direction:

                    approach = opposite(
                        direction
                    )

                    result[approach] += 1

        return result

    # ========================================================

    def get_state(self, node):

        q = self.queue_counts(node)

        light = self.lights[node]

        phase = (
            0
            if light.phase == "NS"
            else 1
        )

        return (
            min(q["N"], 5),
            min(q["E"], 5),
            min(q["S"], 5),
            min(q["W"], 5),
            phase
        )

    # ========================================================

    def ai_update(self):

        if not self.ai_enabled:
            return

        for node in INTERSECTIONS:

            state = self.get_state(node)

            if node in self.last_states:

                old_state = (
                    self.last_states[node]
                )

                if node in self.last_actions:

                    action = (
                        self.last_actions[node]
                    )

                    q = self.queue_counts(
                        node
                    )

                    queue_total = sum(
                        q.values()
                    )

                    reward = -queue_total

                    self.ai.learn(
                        old_state,
                        action,
                        reward,
                        state
                    )

            self.last_states[node] = state

            light = self.lights[node]

            # AI decision point
            if (
                light.state == "GREEN"
                and
                light.timer <= 2
            ):

                action = self.ai.choose(
                    state
                )

                self.last_actions[node] = action

                if action == 1:
                    desired = "NS"

                elif action == 2:
                    desired = "EW"

                else:
                    desired = light.phase

                if desired != light.phase:

                    light.request(
                        desired
                    )

    # ========================================================
    # SPAWN
    # ========================================================

    def spawn_car(self):

        if len(self.cars) >= MAX_CARS:
            return

        car = Car(self)

        self.cars.append(
            car
        )

        self.spawned += 1

    # ========================================================

    def update(self):

        for car in self.cars:
            car.update()

        for car in list(self.cars):

            if car.finished:

                if car.body:

                    self.canvas.delete(
                        car.body
                    )

                self.cars.remove(
                    car
                )

    # ========================================================

    def draw_cars(self):

        for car in self.cars:
            car.draw()

    # ========================================================

    def update_lights(self):

        for light in self.lights.values():
            light.update()

    # ========================================================

    def toggle_ai(self):

        self.ai_enabled = (
            not self.ai_enabled
        )

        if self.ai_enabled:

            self.ai_label.config(
                text="AI: ON",
                fg="#30d158"
            )

        else:

            self.ai_label.config(
                text="AI: OFF",
                fg="#ff453a"
            )

    # ========================================================

    def change_speed(self, amount):

        self.speed = max(
            1,
            min(
                5,
                self.speed + amount
            )
        )

    # ========================================================

    def reset(self):

        for car in self.cars:

            if car.body:

                self.canvas.delete(
                    car.body
                )

        self.cars.clear()

        self.completed = 0
        self.spawned = 0

    # ========================================================

    def clear_qtable(self):

        self.ai.q.clear()

        self.last_states.clear()
        self.last_actions.clear()

        try:

            if os.path.exists(
                QTABLE_FILE
            ):

                os.remove(
                    QTABLE_FILE
                )

        except Exception:
            pass

    # ========================================================

    def update_stats(self):

        queue_total = 0

        for node in INTERSECTIONS:

            q = self.queue_counts(
                node
            )

            queue_total += sum(
                q.values()
            )

        if self.cars:

            average_wait = (
                sum(
                    c.wait
                    for c in self.cars
                )
                /
                len(self.cars)
            )

        else:

            average_wait = 0

        self.stats.config(
            text=
            f"Cars: {len(self.cars)}\n"
            f"Spawned: {self.spawned}\n"
            f"Completed: {self.completed}\n"
            f"Queue: {queue_total}\n"
            f"Avg wait: {average_wait:.1f}\n"
            f"Speed: x{self.speed}\n"
            f"Q states: {len(self.ai.q)}\n"
            f"Epsilon: {self.ai.epsilon:.3f}"
        )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    def loop(self):

        self.tick += 1

        # -----------------------------
        # Spawn
        # -----------------------------

        if self.tick % SPAWN_INTERVAL == 0:

            self.spawn_car()

        # -----------------------------
        # Simulation
        # -----------------------------

        for _ in range(self.speed):

            self.ai_update()

            self.update_lights()

            self.update()

        # -----------------------------
        # Rendering
        # -----------------------------

        self.draw_lights()

        self.draw_cars()

        self.update_stats()

        # -----------------------------
        # Save learning
        # -----------------------------

        if self.tick % 300 == 0:

            self.ai.save()

        self.root.after(
            FRAME_MS,
            self.loop
        )


# ============================================================
# START
# ============================================================

root = tk.Tk()

root.title(
    "SmartTrafficAI v2.6 — AI Traffic Control"
)

root.geometry(
    f"{WIDTH + 260}x{HEIGHT}"
)

root.resizable(
    False,
    False
)

app = Simulation(root)

root.mainloop()


import tkinter as tk
import random
import time

# ============================================================
# TRAFFIC ENGINE v3.0
# Deterministic traffic engine - NO AI
# ============================================================

WIDTH = 1200
HEIGHT = 800

ROAD_W = 110
LANE_W = 27
LANE_OFFSET = 27

CAR_W = 16
CAR_H = 10

CAR_SPEED = 2.2
MIN_GAP = 32

GREEN_TIME = 180
YELLOW_TIME = 35

INTERSECTIONS = [
    (360, 250),
    (840, 250),
    (360, 550),
    (840, 550),
]

DIRECTIONS = ["N", "S", "E", "W"]

VEC = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}

OPPOSITE = {
    "N": "S",
    "S": "N",
    "E": "W",
    "W": "E",
}


# ============================================================
# INTERSECTION CONTROLLER
# ============================================================

class Intersection:

    def __init__(self, x, y):
        self.x = x
        self.y = y

        # 0 = NS green
        # 1 = NS yellow
        # 2 = EW green
        # 3 = EW yellow
        self.phase = 0
        self.timer = 0

    def update(self):
        self.timer += 1

        if self.phase == 0 and self.timer >= GREEN_TIME:
            self.phase = 1
            self.timer = 0

        elif self.phase == 1 and self.timer >= YELLOW_TIME:
            self.phase = 2
            self.timer = 0

        elif self.phase == 2 and self.timer >= GREEN_TIME:
            self.phase = 3
            self.timer = 0

        elif self.phase == 3 and self.timer >= YELLOW_TIME:
            self.phase = 0
            self.timer = 0

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

        names = {
            0: "N/S GREEN",
            1: "N/S YELLOW",
            2: "E/W GREEN",
            3: "E/W YELLOW"
        }

        return names[self.phase]


# ============================================================
# CAR
# ============================================================

class Car:

    def __init__(self, canvas, direction, spawn, target):

        self.canvas = canvas

        self.direction = direction
        self.x, self.y = spawn

        self.target = target

        self.speed = CAR_SPEED
        self.waiting = False
        self.passed = False

        self.id = None

        self.color = random.choice([
            "#00d4ff",
            "#4ade80",
            "#facc15",
            "#fb7185",
            "#c084fc",
            "#fb923c",
            "#e879f9",
            "#38bdf8"
        ])

        self.create()

    # --------------------------------------------------------

    def create(self):

        self.id = self.canvas.create_rectangle(
            self.x - CAR_W / 2,
            self.y - CAR_H / 2,
            self.x + CAR_W / 2,
            self.y + CAR_H / 2,
            fill=self.color,
            outline=""
        )

    # --------------------------------------------------------

    def approach_for_target(self):

        tx, ty = self.target

        if self.direction == "N":
            return "S"

        if self.direction == "S":
            return "N"

        if self.direction == "E":
            return "W"

        return "E"

    # --------------------------------------------------------

    def stop_line(self):

        tx, ty = self.target

        gap = 78

        approach = self.approach_for_target()

        if approach == "N":
            return ("y", ty - gap)

        if approach == "S":
            return ("y", ty + gap)

        if approach == "E":
            return ("x", tx + gap)

        return ("x", tx - gap)

    # --------------------------------------------------------

    def crossed_stop_line(self):

        axis, line = self.stop_line()

        if axis == "y":

            if self.direction == "N":
                return self.y < line

            return self.y > line

        else:

            if self.direction == "E":
                return self.x > line

            return self.x < line

    # --------------------------------------------------------

    def would_cross_stop_line(self):

        axis, line = self.stop_line()

        dx, dy = VEC[self.direction]

        nx = self.x + dx * self.speed
        ny = self.y + dy * self.speed

        if axis == "y":

            if self.direction == "N":
                return self.y >= line and ny < line

            if self.direction == "S":
                return self.y <= line and ny > line

        else:

            if self.direction == "E":
                return self.x <= line and nx > line

            if self.direction == "W":
                return self.x >= line and nx < line

        return False

    # --------------------------------------------------------

    def clamp_to_stop_line(self):

        axis, line = self.stop_line()

        if axis == "y":
            self.y = line

        else:
            self.x = line

    # --------------------------------------------------------

    def distance_to_stop_line(self):

        axis, line = self.stop_line()

        if axis == "y":
            return abs(self.y - line)

        return abs(self.x - line)

    # --------------------------------------------------------

    def inside_intersection(self):

        tx, ty = self.target

        half = 63

        return (
            tx - half <= self.x <= tx + half and
            ty - half <= self.y <= ty + half
        )

    # --------------------------------------------------------

    def near_car(self, cars):

        for other in cars:

            if other is self:
                continue

            if other.direction != self.direction:
                continue

            if other.target != self.target:
                continue

            dx = other.x - self.x
            dy = other.y - self.y

            if self.direction == "N" and dy < 0 and abs(dx) < 22:
                if abs(dy) < MIN_GAP:
                    return True

            elif self.direction == "S" and dy > 0 and abs(dx) < 22:
                if abs(dy) < MIN_GAP:
                    return True

            elif self.direction == "E" and dx > 0 and abs(dy) < 22:
                if abs(dx) < MIN_GAP:
                    return True

            elif self.direction == "W" and dx < 0 and abs(dy) < 22:
                if abs(dx) < MIN_GAP:
                    return True

        return False

    # --------------------------------------------------------

    def update(self, engine):

        self.waiting = False

        intersection = engine.intersection_map[self.target]

        approach = self.approach_for_target()

        light = intersection.light_for(approach)

        # ----------------------------------------------------
        # RED / YELLOW SAFETY
        # ----------------------------------------------------

        if not self.crossed_stop_line():

            if light != "green":

                if self.would_cross_stop_line():

                    self.clamp_to_stop_line()

                self.waiting = True
                self.speed = 0

                self.draw()
                return

        # ----------------------------------------------------
        # CAR FOLLOWING
        # ----------------------------------------------------

        if self.near_car(engine.cars):

            self.speed = 0
            self.waiting = True

            self.draw()
            return

        # ----------------------------------------------------
        # NORMAL MOVEMENT
        # ----------------------------------------------------

        self.speed = CAR_SPEED

        dx, dy = VEC[self.direction]

        self.x += dx * self.speed
        self.y += dy * self.speed

        # ----------------------------------------------------
        # PASSED INTERSECTION
        # ----------------------------------------------------

        if not self.passed:

            if self.crossed_stop_line():
                self.passed = True
                engine.total_passed += 1

        self.draw()

    # --------------------------------------------------------

    def draw(self):

        self.canvas.coords(
            self.id,
            self.x - CAR_W / 2,
            self.y - CAR_H / 2,
            self.x + CAR_W / 2,
            self.y + CAR_H / 2
        )

    # --------------------------------------------------------

    def outside(self):

        return (
            self.x < -80 or
            self.x > WIDTH + 80 or
            self.y < -80 or
            self.y > HEIGHT + 80
        )


# ============================================================
# TRAFFIC ENGINE
# ============================================================

class TrafficEngine:

    def __init__(self, canvas):

        self.canvas = canvas

        self.intersections = [
            Intersection(*p)
            for p in INTERSECTIONS
        ]

        self.intersection_map = {
            p: self.intersections[i]
            for i, p in enumerate(INTERSECTIONS)
        }

        self.cars = []

        self.total_spawned = 0
        self.total_passed = 0

        self.running = True

        self.spawn_timer = 0

        self.create_city()

    # --------------------------------------------------------

    def create_city(self):

        self.canvas.configure(bg="#07111f")

        # Background
        self.canvas.create_rectangle(
            0, 0,
            WIDTH,
            HEIGHT,
            fill="#07111f",
            outline=""
        )

        # subtle grid
        for x in range(0, WIDTH, 40):

            self.canvas.create_line(
                x, 0, x, HEIGHT,
                fill="#0b1728"
            )

        for y in range(0, HEIGHT, 40):

            self.canvas.create_line(
                0, y, WIDTH, y,
                fill="#0b1728"
            )

        # Roads
        for x, y in INTERSECTIONS:

            self.canvas.create_rectangle(
                x - ROAD_W / 2,
                0,
                x + ROAD_W / 2,
                HEIGHT,
                fill="#182535",
                outline=""
            )

            self.canvas.create_rectangle(
                0,
                y - ROAD_W / 2,
                WIDTH,
                y + ROAD_W / 2,
                fill="#182535",
                outline=""
            )

        # Lane markings
        for x, y in INTERSECTIONS:

            self.canvas.create_line(
                x,
                0,
                x,
                HEIGHT,
                fill="#334155",
                dash=(14, 14)
            )

            self.canvas.create_line(
                0,
                y,
                WIDTH,
                y,
                fill="#334155",
                dash=(14, 14)
            )

        # Intersections
        for x, y in INTERSECTIONS:

            self.canvas.create_rectangle(
                x - 63,
                y - 63,
                x + 63,
                y + 63,
                fill="#202d3d",
                outline="#475569",
                width=2
            )

        self.draw_stop_lines()
        self.create_traffic_lights()

    # --------------------------------------------------------

    def lane_position(self, direction, x, y):

        if direction == "N":
            return x + LANE_OFFSET, y

        if direction == "S":
            return x - LANE_OFFSET, y

        if direction == "E":
            return x, y - LANE_OFFSET

        return x, y + LANE_OFFSET

    # --------------------------------------------------------

    def draw_stop_lines(self):

        for x, y in INTERSECTIONS:

            # NORTH APPROACH
            self.canvas.create_line(
                x - 42,
                y - 78,
                x + 42,
                y - 78,
                fill="#f8fafc",
                width=4
            )

            # SOUTH APPROACH
            self.canvas.create_line(
                x - 42,
                y + 78,
                x + 42,
                y + 78,
                fill="#f8fafc",
                width=4
            )

            # WEST APPROACH
            self.canvas.create_line(
                x - 78,
                y - 42,
                x - 78,
                y + 42,
                fill="#f8fafc",
                width=4
            )

            # EAST APPROACH
            self.canvas.create_line(
                x + 78,
                y - 42,
                x + 78,
                y + 42,
                fill="#f8fafc",
                width=4
            )

    # --------------------------------------------------------

    def spawn_car(self):

        # Pick one of the four intersections
        target = random.choice(INTERSECTIONS)

        tx, ty = target

        direction = random.choice(DIRECTIONS)

        if direction == "N":

            x = tx + LANE_OFFSET
            y = HEIGHT + 50

        elif direction == "S":

            x = tx - LANE_OFFSET
            y = -50

        elif direction == "E":

            x = -50
            y = ty - LANE_OFFSET

        else:

            x = WIDTH + 50
            y = ty + LANE_OFFSET

        car = Car(
            self.canvas,
            direction,
            (x, y),
            target
        )

        self.cars.append(car)

        self.total_spawned += 1

    # --------------------------------------------------------

    def update(self):

        if not self.running:
            return

        # Lights
        for intersection in self.intersections:
            intersection.update()

        # Spawn
        self.spawn_timer += 1

        if self.spawn_timer >= 35:

            self.spawn_timer = 0

            if len(self.cars) < 55:
                self.spawn_car()

        # Cars
        for car in list(self.cars):

            car.update(self)

            if car.outside():

                self.canvas.delete(car.id)

                self.cars.remove(car)

        # Traffic lights visual update
        self.update_traffic_lights()

        # UI
        self.update_monitor()

    # --------------------------------------------------------


    # --------------------------------------------------------
    # TRAFFIC LIGHTS VISUALS
    # --------------------------------------------------------

    def create_traffic_lights(self):

        self.light_objects = []

        for intersection in self.intersections:

            x = intersection.x
            y = intersection.y

            # هر تقاطع 4 چراغ دارد:
            # N = چراغ ورودی شمال
            # S = چراغ ورودی جنوب
            # E = چراغ ورودی شرق
            # W = چراغ ورودی غرب

            positions = {
                "N": (x + 48, y - 82),
                "S": (x - 48, y + 82),
                "E": (x + 82, y + 48),
                "W": (x - 82, y - 48)
            }

            for approach, (lx, ly) in positions.items():

                # قاب چراغ
                if approach in ("N", "S"):

                    frame = self.canvas.create_rectangle(
                        lx - 9,
                        ly - 22,
                        lx + 9,
                        ly + 22,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                else:

                    frame = self.canvas.create_rectangle(
                        lx - 22,
                        ly - 9,
                        lx + 22,
                        ly + 9,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                # سه لامپ
                lights = []

                for i in range(3):

                    if approach in ("N", "S"):

                        cy = ly - 13 + i * 13

                        item = self.canvas.create_oval(
                            lx - 5,
                            cy - 5,
                            lx + 5,
                            cy + 5,
                            fill="#18202b",
                            outline="#334155"
                        )

                    else:

                        cx = lx - 13 + i * 13

                        item = self.canvas.create_oval(
                            cx - 5,
                            ly - 5,
                            cx + 5,
                            ly + 5,
                            fill="#18202b",
                            outline="#334155"
                        )

                    lights.append(item)

                self.light_objects.append({
                    "intersection": intersection,
                    "approach": approach,
                    "frame": frame,
                    "lights": lights
                })

        self.update_traffic_lights()

    # --------------------------------------------------------

    def update_traffic_lights(self):

        if not hasattr(self, "light_objects"):
            return

        for obj in self.light_objects:

            intersection = obj["intersection"]
            approach = obj["approach"]

            state = intersection.light_for(approach)

            lights = obj["lights"]

            # ترتیب:
            # 0 = قرمز
            # 1 = زرد
            # 2 = سبز

            colors = [
                "#450a0a",
                "#453800",
                "#052e16"
            ]

            for i in range(3):

                self.canvas.itemconfig(
                    lights[i],
                    fill=colors[i]
                )

            if state == "red":

                self.canvas.itemconfig(
                    lights[0],
                    fill="#ef4444"
                )

            elif state == "yellow":

                self.canvas.itemconfig(
                    lights[1],
                    fill="#facc15"
                )

            elif state == "green":

                self.canvas.itemconfig(
                    lights[2],
                    fill="#22c55e"
                )
    def update_monitor(self):

        if not hasattr(self, "monitor_callback"):
            return

        waiting = sum(
            1 for c in self.cars
            if c.waiting
        )

        self.monitor_callback(
            len(self.cars),
            self.total_spawned,
            self.total_passed,
            waiting
        )

    # --------------------------------------------------------

    def reset(self):

        for car in self.cars:

            self.canvas.delete(car.id)

        self.cars.clear()

        self.total_spawned = 0
        self.total_passed = 0

        self.spawn_timer = 0

        for intersection in self.intersections:

            intersection.phase = 0
            intersection.timer = 0


# ============================================================
# UI
# ============================================================

class App:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            "Traffic Engine v3.0 — Deterministic Traffic Simulation"
        )

        self.root.geometry("1450x850")
        self.root.configure(bg="#050b14")

        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            self.root,
            width=WIDTH,
            height=HEIGHT,
            bg="#07111f",
            highlightthickness=0
        )

        self.canvas.pack(
            side="left",
            padx=15,
            pady=15
        )

        self.panel = tk.Frame(
            self.root,
            width=200,
            height=800,
            bg="#0b1422"
        )

        self.panel.pack(
            side="right",
            fill="y",
            padx=(0, 15),
            pady=15
        )

        self.create_panel()

        self.engine = TrafficEngine(self.canvas)

        self.engine.monitor_callback = self.update_monitor

        self.paused = False

        self.root.bind(
            "<space>",
            self.toggle_pause
        )

        self.root.bind(
            "r",
            self.reset
        )

        self.root.bind(
            "<Up>",
            self.speed_up
        )

        self.root.bind(
            "<Down>",
            self.speed_down
        )

        self.loop()

    # --------------------------------------------------------

    def create_panel(self):

        title = tk.Label(
            self.panel,
            text="TRAFFIC\nMONITOR",
            font=("Segoe UI", 18, "bold"),
            fg="#e2e8f0",
            bg="#0b1422"
        )

        title.pack(
            pady=(25, 25)
        )

        self.status = tk.Label(
            self.panel,
            text="● RUNNING",
            font=("Segoe UI", 11, "bold"),
            fg="#4ade80",
            bg="#0b1422"
        )

        self.status.pack(
            pady=5
        )

        self.line()

        self.cars_label = self.metric(
            "Cars",
            "0"
        )

        self.spawn_label = self.metric(
            "Spawned",
            "0"
        )

        self.passed_label = self.metric(
            "Passed",
            "0"
        )

        self.waiting_label = self.metric(
            "Waiting",
            "0"
        )

        self.line()

        self.phase_title = tk.Label(
            self.panel,
            text="INTERSECTIONS",
            font=("Segoe UI", 10, "bold"),
            fg="#94a3b8",
            bg="#0b1422"
        )

        self.phase_title.pack(
            pady=(10, 5)
        )

        self.phase_labels = []

        for i in range(4):

            label = tk.Label(
                self.panel,
                text=f"I{i+1}: N/S GREEN",
                font=("Consolas", 9),
                fg="#4ade80",
                bg="#0b1422",
                anchor="w"
            )

            label.pack(
                fill="x",
                padx=15,
                pady=3
            )

            self.phase_labels.append(label)

        self.line()

        info = tk.Label(
            self.panel,
            text=(
                "CONTROLS\n\n"
                "SPACE  Pause\n"
                "R      Reset\n"
                "↑      Faster\n"
                "↓      Slower\n\n"
                "AI: OFF\n"
                "Mode: Deterministic\n\n"
                "Red → Stop\n"
                "Yellow → Stop\n"
                "Green → Go"
            ),
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0b1422",
            justify="left"
        )

        info.pack(
            pady=20,
            padx=15,
            anchor="w"
        )

    # --------------------------------------------------------

    def line(self):

        tk.Frame(
            self.panel,
            height=1,
            bg="#1e293b"
        ).pack(
            fill="x",
            padx=15,
            pady=12
        )

    # --------------------------------------------------------

    def metric(self, name, value):

        frame = tk.Frame(
            self.panel,
            bg="#0b1422"
        )

        frame.pack(
            fill="x",
            padx=15,
            pady=7
        )

        label = tk.Label(
            frame,
            text=name,
            font=("Segoe UI", 9),
            fg="#64748b",
            bg="#0b1422"
        )

        label.pack(
            anchor="w"
        )

        value_label = tk.Label(
            frame,
            text=value,
            font=("Segoe UI", 18, "bold"),
            fg="#f8fafc",
            bg="#0b1422"
        )

        value_label.pack(
            anchor="w"
        )

        return value_label

    # --------------------------------------------------------


    # --------------------------------------------------------
    # TRAFFIC LIGHTS VISUALS
    # --------------------------------------------------------

    def create_traffic_lights(self):

        self.light_objects = []

        for intersection in self.intersections:

            x = intersection.x
            y = intersection.y

            # هر تقاطع 4 چراغ دارد:
            # N = چراغ ورودی شمال
            # S = چراغ ورودی جنوب
            # E = چراغ ورودی شرق
            # W = چراغ ورودی غرب

            positions = {
                "N": (x + 48, y - 82),
                "S": (x - 48, y + 82),
                "E": (x + 82, y + 48),
                "W": (x - 82, y - 48)
            }

            for approach, (lx, ly) in positions.items():

                # قاب چراغ
                if approach in ("N", "S"):

                    frame = self.canvas.create_rectangle(
                        lx - 9,
                        ly - 22,
                        lx + 9,
                        ly + 22,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                else:

                    frame = self.canvas.create_rectangle(
                        lx - 22,
                        ly - 9,
                        lx + 22,
                        ly + 9,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                # سه لامپ
                lights = []

                for i in range(3):

                    if approach in ("N", "S"):

                        cy = ly - 13 + i * 13

                        item = self.canvas.create_oval(
                            lx - 5,
                            cy - 5,
                            lx + 5,
                            cy + 5,
                            fill="#18202b",
                            outline="#334155"
                        )

                    else:

                        cx = lx - 13 + i * 13

                        item = self.canvas.create_oval(
                            cx - 5,
                            ly - 5,
                            cx + 5,
                            ly + 5,
                            fill="#18202b",
                            outline="#334155"
                        )

                    lights.append(item)

                self.light_objects.append({
                    "intersection": intersection,
                    "approach": approach,
                    "frame": frame,
                    "lights": lights
                })

        self.update_traffic_lights()

    # --------------------------------------------------------

    def update_traffic_lights(self):

        if not hasattr(self, "light_objects"):
            return

        for obj in self.light_objects:

            intersection = obj["intersection"]
            approach = obj["approach"]

            state = intersection.light_for(approach)

            lights = obj["lights"]

            # ترتیب:
            # 0 = قرمز
            # 1 = زرد
            # 2 = سبز

            colors = [
                "#450a0a",
                "#453800",
                "#052e16"
            ]

            for i in range(3):

                self.canvas.itemconfig(
                    lights[i],
                    fill=colors[i]
                )

            if state == "red":

                self.canvas.itemconfig(
                    lights[0],
                    fill="#ef4444"
                )

            elif state == "yellow":

                self.canvas.itemconfig(
                    lights[1],
                    fill="#facc15"
                )

            elif state == "green":

                self.canvas.itemconfig(
                    lights[2],
                    fill="#22c55e"
                )
    def update_monitor(
        self,
        cars,
        spawned,
        passed,
        waiting
    ):

        self.cars_label.config(
            text=str(cars)
        )

        self.spawn_label.config(
            text=str(spawned)
        )

        self.passed_label.config(
            text=str(passed)
        )

        self.waiting_label.config(
            text=str(waiting)
        )

        for i, intersection in enumerate(
            self.engine.intersections
        ):

            self.phase_labels[i].config(
                text=f"I{i+1}: {intersection.phase_name()}"
            )

            if "GREEN" in intersection.phase_name():

                self.phase_labels[i].config(
                    fg="#4ade80"
                )

            elif "YELLOW" in intersection.phase_name():

                self.phase_labels[i].config(
                    fg="#facc15"
                )

            else:

                self.phase_labels[i].config(
                    fg="#fb7185"
                )

    # --------------------------------------------------------

    def toggle_pause(self, event=None):

        self.paused = not self.paused

        if self.paused:

            self.engine.running = False

            self.status.config(
                text="● PAUSED",
                fg="#facc15"
            )

        else:

            self.engine.running = True

            self.status.config(
                text="● RUNNING",
                fg="#4ade80"
            )

    # --------------------------------------------------------

    def reset(self, event=None):

        self.engine.reset()

    # --------------------------------------------------------

    def speed_up(self, event=None):

        global CAR_SPEED

        CAR_SPEED = min(
            5.0,
            CAR_SPEED + 0.3
        )

    # --------------------------------------------------------

    def speed_down(self, event=None):

        global CAR_SPEED

        CAR_SPEED = max(
            0.5,
            CAR_SPEED - 0.3
        )

    # --------------------------------------------------------

    def loop(self):

        self.engine.update()

        self.root.after(
            16,
            self.loop
        )

    # --------------------------------------------------------

    def run(self):

        self.root.mainloop()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app = App()
    app.run()


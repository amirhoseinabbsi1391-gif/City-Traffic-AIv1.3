import tkinter as tk
import random

# ============================================================
# TRAFFIC ENGINE v3.2
# Deterministic / No AI
# ============================================================

WIDTH = 1200
HEIGHT = 800

ROAD_W = 110
LANE_OFFSET = 27

CAR_W = 16
CAR_H = 10

CAR_SPEED = 2.2
MIN_GAP = 34

GREEN_TIME = 180
YELLOW_TIME = 35

INTERSECTIONS = [
    (360, 250),
    (840, 250),
    (360, 550),
    (840, 550)
]

DIRECTIONS = ["N", "S", "E", "W"]

VEC = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0)
}


# ============================================================
# INTERSECTION
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

    def name(self):

        return {
            0: "N/S GREEN",
            1: "N/S YELLOW",
            2: "E/W GREEN",
            3: "E/W YELLOW"
        }[self.phase]


# ============================================================
# CAR
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

        # ----------------------------------------------------
        # STATE MACHINE
        #
        # APPROACHING
        # WAITING
        # ENTERED
        # CROSSING
        # EXITED
        # ----------------------------------------------------

        self.state = "APPROACHING"

        self.passed = False

        self.color = random.choice([
            "#00d4ff",
            "#4ade80",
            "#facc15",
            "#fb7185",
            "#c084fc",
            "#fb923c",
            "#38bdf8",
            "#e879f9"
        ])

        self.spawn()

        self.id = self.canvas.create_rectangle(
            self.x - CAR_W / 2,
            self.y - CAR_H / 2,
            self.x + CAR_W / 2,
            self.y + CAR_H / 2,
            fill=self.color,
            outline=""
        )

    # --------------------------------------------------------

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

    # --------------------------------------------------------

    def approach(self):

        if self.direction == "N":
            return "S"

        if self.direction == "S":
            return "N"

        if self.direction == "E":
            return "W"

        return "E"

    # --------------------------------------------------------
    # EXACT STOP LINE
    # --------------------------------------------------------

    def stop_line(self):

        tx, ty = self.target

        gap = 78

        if self.direction == "N":
            return ("y", ty + gap)

        if self.direction == "S":
            return ("y", ty - gap)

        if self.direction == "E":
            return ("x", tx - gap)

        return ("x", tx + gap)

    # --------------------------------------------------------

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

    def would_cross_line(self):

        axis, line = self.stop_line()

        nx = self.x + VEC[self.direction][0] * CAR_SPEED
        ny = self.y + VEC[self.direction][1] * CAR_SPEED

        if axis == "y":

            if self.direction == "N":
                return self.y >= line and ny < line

            return self.y <= line and ny > line

        else:

            if self.direction == "E":
                return self.x <= line and nx > line

            return self.x >= line and nx < line

    # --------------------------------------------------------

    def clamp_line(self):

        axis, line = self.stop_line()

        if axis == "y":
            self.y = line

        else:
            self.x = line

    # --------------------------------------------------------

    def inside_intersection(self):

        tx, ty = self.target

        half = 63

        return (
            tx - half <= self.x <= tx + half and
            ty - half <= self.y <= ty + half
        )

    # --------------------------------------------------------

    def close_to_car(self, cars):

        for other in cars:

            if other is self:
                continue

            if other.direction != self.direction:
                continue

            if other.target != self.target:
                continue

            dx = other.x - self.x
            dy = other.y - self.y

            if self.direction == "N":

                if dy < 0 and abs(dx) < 20 and abs(dy) < MIN_GAP:
                    return True

            elif self.direction == "S":

                if dy > 0 and abs(dx) < 20 and abs(dy) < MIN_GAP:
                    return True

            elif self.direction == "E":

                if dx > 0 and abs(dy) < 20 and abs(dx) < MIN_GAP:
                    return True

            elif self.direction == "W":

                if dx < 0 and abs(dy) < 20 and abs(dx) < MIN_GAP:
                    return True

        return False

    # --------------------------------------------------------

    def move(self):

        dx, dy = VEC[self.direction]

        self.x += dx * CAR_SPEED
        self.y += dy * CAR_SPEED

    # --------------------------------------------------------

    def update(self, engine):

        self.waiting = False

        intersection = engine.intersection_map[self.target]

        # ====================================================
        # 1. APPROACHING
        # ====================================================

        if self.state == "APPROACHING":

            # فقط تا قبل از خط توقف چراغ مهم است.
            if self.before_stop_line():

                light = intersection.light_for(
                    self.approach()
                )

                # --------------------------------------------
                # RED / YELLOW
                # --------------------------------------------

                if light != "green":

                    if self.would_cross_line():
                        self.clamp_line()

                    self.speed = 0
                    self.waiting = True
                    self.state = "WAITING"

                    self.draw()
                    return

                # --------------------------------------------
                # GREEN
                # --------------------------------------------

                if self.close_to_car(engine.cars):

                    self.speed = 0
                    self.waiting = True

                    self.draw()
                    return

                self.speed = CAR_SPEED
                self.move()

                # اگر خط را رد کرد:
                if self.crossed_stop_line():

                    self.state = "ENTERED"
                    self.passed = True

                    engine.total_passed += 1

                self.draw()
                return

        # ====================================================
        # 2. WAITING
        # ====================================================

        if self.state == "WAITING":

            # ------------------------------------------------
            # مهم:
            # اگر چراغ سبز شده، دوباره حرکت کن.
            # ------------------------------------------------

            light = intersection.light_for(
                self.approach()
            )

            if light == "green":

                if not self.close_to_car(engine.cars):

                    self.state = "APPROACHING"
                    self.speed = CAR_SPEED

                else:

                    self.speed = 0
                    self.waiting = True

            else:

                self.speed = 0
                self.waiting = True

            # -----------------------------------------------
            # حرکت فقط اگر مجاز باشد
            # -----------------------------------------------

            if self.speed > 0:

                self.move()

                if self.crossed_stop_line():

                    self.state = "ENTERED"
                    self.passed = True

                    engine.total_passed += 1

            self.draw()
            return

        # ====================================================
        # 3. ENTERED
        # ====================================================

        if self.state == "ENTERED":

            # ------------------------------------------------
            # از اینجا به بعد چراغ کاملاً نادیده گرفته می‌شود.
            # ------------------------------------------------

            self.speed = CAR_SPEED
            self.move()

            if not self.inside_intersection():

                self.state = "CROSSING"

            self.draw()
            return

        # ====================================================
        # 4. CROSSING
        # ====================================================

        if self.state == "CROSSING":

            # ------------------------------------------------
            # چراغ دیگر هیچ اثری ندارد.
            # ------------------------------------------------

            self.speed = CAR_SPEED
            self.move()

            self.draw()
            return

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
            self.x < -100 or
            self.x > WIDTH + 100 or
            self.y < -100 or
            self.y > HEIGHT + 100
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

        self.canvas.configure(
            bg="#07111f"
        )

        # Background
        self.canvas.create_rectangle(
            0,
            0,
            WIDTH,
            HEIGHT,
            fill="#07111f",
            outline=""
        )

        # Grid
        for x in range(0, WIDTH, 40):

            self.canvas.create_line(
                x,
                0,
                x,
                HEIGHT,
                fill="#0b1728"
            )

        for y in range(0, HEIGHT, 40):

            self.canvas.create_line(
                0,
                y,
                WIDTH,
                y,
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

    def draw_stop_lines(self):

        for x, y in INTERSECTIONS:

            # NORTH
            self.canvas.create_line(
                x - 42,
                y - 78,
                x + 42,
                y - 78,
                fill="#f8fafc",
                width=4
            )

            # SOUTH
            self.canvas.create_line(
                x - 42,
                y + 78,
                x + 42,
                y + 78,
                fill="#f8fafc",
                width=4
            )

            # WEST
            self.canvas.create_line(
                x - 78,
                y - 42,
                x - 78,
                y + 42,
                fill="#f8fafc",
                width=4
            )

            # EAST
            self.canvas.create_line(
                x + 78,
                y - 42,
                x + 78,
                y + 42,
                fill="#f8fafc",
                width=4
            )

    # --------------------------------------------------------
    # LIGHTS
    # --------------------------------------------------------

    def create_traffic_lights(self):

        self.light_objects = []

        for intersection in self.intersections:

            x = intersection.x
            y = intersection.y

            positions = {
                "N": (x + 48, y - 88),
                "S": (x - 48, y + 88),
                "E": (x + 88, y + 48),
                "W": (x - 88, y - 48)
            }

            for approach, (lx, ly) in positions.items():

                if approach in ("N", "S"):

                    frame = self.canvas.create_rectangle(
                        lx - 9,
                        ly - 23,
                        lx + 9,
                        ly + 23,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                else:

                    frame = self.canvas.create_rectangle(
                        lx - 23,
                        ly - 9,
                        lx + 23,
                        ly + 9,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                lights = []

                for i in range(3):

                    if approach in ("N", "S"):

                        cy = ly - 14 + i * 14

                        item = self.canvas.create_oval(
                            lx - 5,
                            cy - 5,
                            lx + 5,
                            cy + 5,
                            fill="#18202b",
                            outline="#334155"
                        )

                    else:

                        cx = lx - 14 + i * 14

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
                    "lights": lights
                })

        self.update_traffic_lights()

    # --------------------------------------------------------

    def update_traffic_lights(self):

        for obj in self.light_objects:

            intersection = obj["intersection"]

            approach = obj["approach"]

            state = intersection.light_for(
                approach
            )

            lights = obj["lights"]

            # Dim inactive bulbs
            for i, color in enumerate([
                "#450a0a",
                "#453800",
                "#052e16"
            ]):

                self.canvas.itemconfig(
                    lights[i],
                    fill=color
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

    # --------------------------------------------------------

    def spawn_car(self):

        target = random.choice(
            INTERSECTIONS
        )

        direction = random.choice(
            DIRECTIONS
        )

        car = Car(
            self.canvas,
            direction,
            target
        )

        # جلوگیری از Spawn خیلی نزدیک به خودرو دیگر
        for existing in self.cars:

            dx = existing.x - car.x
            dy = existing.y - car.y

            if abs(dx) < 30 and abs(dy) < 30:

                self.canvas.delete(car.id)
                return

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

        if self.spawn_timer >= 32:

            self.spawn_timer = 0

            if len(self.cars) < 60:

                self.spawn_car()

        # Cars
        for car in list(self.cars):

            car.update(self)

            if car.outside():

                self.canvas.delete(car.id)

                if car in self.cars:
                    self.cars.remove(car)

        # Visual lights
        self.update_traffic_lights()

        # Monitoring
        if hasattr(
            self,
            "monitor_callback"
        ):

            waiting = sum(
                1
                for car in self.cars
                if car.waiting
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

            self.canvas.delete(
                car.id
            )

        self.cars.clear()

        self.total_spawned = 0
        self.total_passed = 0
        self.spawn_timer = 0

        for intersection in self.intersections:

            intersection.phase = 0
            intersection.timer = 0


# ============================================================
# USER INTERFACE
# ============================================================

class App:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            "Traffic Engine v3.2 — City Traffic Simulation"
        )

        self.root.geometry(
            "1450x850"
        )

        self.root.configure(
            bg="#050b14"
        )

        self.root.resizable(
            False,
            False
        )

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

        self.engine = TrafficEngine(
            self.canvas
        )

        self.engine.monitor_callback = (
            self.update_monitor
        )

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

        self.status.pack()

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

        label = tk.Label(
            self.panel,
            text="INTERSECTIONS",
            font=("Segoe UI", 10, "bold"),
            fg="#94a3b8",
            bg="#0b1422"
        )

        label.pack(
            pady=5
        )

        self.phase_labels = []

        for i in range(4):

            item = tk.Label(
                self.panel,
                text=f"I{i+1}: N/S GREEN",
                font=("Consolas", 9),
                fg="#4ade80",
                bg="#0b1422",
                anchor="w"
            )

            item.pack(
                fill="x",
                padx=15,
                pady=3
            )

            self.phase_labels.append(
                item
            )

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
                "ENGINE: v3.2\n\n"
                "RED → STOP\n"
                "YELLOW → STOP\n"
                "GREEN → GO"
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

        tk.Label(
            frame,
            text=name,
            font=("Segoe UI", 9),
            fg="#64748b",
            bg="#0b1422"
        ).pack(
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

            name = intersection.name()

            self.phase_labels[i].config(
                text=f"I{i+1}: {name}"
            )

            if "GREEN" in name:

                self.phase_labels[i].config(
                    fg="#4ade80"
                )

            elif "YELLOW" in name:

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

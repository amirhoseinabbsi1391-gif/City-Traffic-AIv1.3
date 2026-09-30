import tkinter as tk
import random

# ============================================================
# TRAFFIC ENGINE v3.3
# Deterministic Traffic Simulation
# AI: OFF
# ============================================================

WIDTH = 1200
HEIGHT = 800

ROAD_W = 110
LANE_OFFSET = 27

CAR_W = 16
CAR_H = 10

CAR_SPEED = 2.2

# فاصله ایمن بین خودروهای قبل از تقاطع
FOLLOW_GAP = 34

# اندازه محدوده تقاطع
INTERSECTION_HALF = 63

# زمان چراغ
GREEN_TIME = 180
YELLOW_TIME = 35

# چهار تقاطع
INTERSECTIONS = [
    (360, 250),
    (840, 250),
    (360, 550),
    (840, 550)
]

DIRECTIONS = ["N", "S", "E", "W"]

VECTOR = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0)
}


# ============================================================
# TRAFFIC LIGHT CONTROLLER
# ============================================================

class Intersection:

    def __init__(self, x, y):

        self.x = x
        self.y = y

        # 0 = N/S GREEN
        # 1 = N/S YELLOW
        # 2 = E/W GREEN
        # 3 = E/W YELLOW

        self.phase = 0
        self.timer = 0

    def update(self):

        self.timer += 1

        if self.phase == 0:
            if self.timer >= GREEN_TIME:
                self.phase = 1
                self.timer = 0

        elif self.phase == 1:
            if self.timer >= YELLOW_TIME:
                self.phase = 2
                self.timer = 0

        elif self.phase == 2:
            if self.timer >= GREEN_TIME:
                self.phase = 3
                self.timer = 0

        elif self.phase == 3:
            if self.timer >= YELLOW_TIME:
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
        # States:
        #
        # APPROACHING
        # WAITING
        # CROSSING
        # EXITED
        # ----------------------------------------------------

        self.state = "APPROACHING"

        # ----------------------------------------------------
        # CRITICAL FLAG
        #
        # وقتی True شود، خودرو وارد تقاطع شده
        # و هیچ چراغی نمی‌تواند آن را متوقف کند.
        # ----------------------------------------------------

        self.intersection_locked = False

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
    # Incoming approach
    # --------------------------------------------------------

    def approach(self):

        # خودرو به سمت شمال حرکت می‌کند
        # پس از جنوب وارد تقاطع می‌شود.

        if self.direction == "N":
            return "S"

        if self.direction == "S":
            return "N"

        if self.direction == "E":
            return "W"

        return "E"

    # --------------------------------------------------------
    # Exact Stop Line
    # --------------------------------------------------------

    def stop_line(self):

        tx, ty = self.target

        STOP_DISTANCE = INTERSECTION_HALF + 15

        if self.direction == "N":

            return (
                "y",
                ty + STOP_DISTANCE
            )

        if self.direction == "S":

            return (
                "y",
                ty - STOP_DISTANCE
            )

        if self.direction == "E":

            return (
                "x",
                tx - STOP_DISTANCE
            )

        return (
            "x",
            tx + STOP_DISTANCE
        )

    # --------------------------------------------------------
    # Conflict Zone
    # --------------------------------------------------------

    def inside_conflict_zone(self):

        tx, ty = self.target

        return (
            tx - INTERSECTION_HALF <= self.x <= tx + INTERSECTION_HALF
            and
            ty - INTERSECTION_HALF <= self.y <= ty + INTERSECTION_HALF
        )

    # --------------------------------------------------------
    # Has crossed stop line?
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Is before stop line?
    # --------------------------------------------------------

    def is_before_stop_line(self):

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
    # Would next movement cross stop line?
    # --------------------------------------------------------

    def would_cross_stop_line(self):

        axis, line = self.stop_line()

        dx, dy = VECTOR[self.direction]

        nx = self.x + dx * CAR_SPEED
        ny = self.y + dy * CAR_SPEED

        if axis == "y":

            if self.direction == "N":

                return (
                    self.y >= line
                    and
                    ny < line
                )

            else:

                return (
                    self.y <= line
                    and
                    ny > line
                )

        else:

            if self.direction == "E":

                return (
                    self.x <= line
                    and
                    nx > line
                )

            else:

                return (
                    self.x >= line
                    and
                    nx < line
                )

    # --------------------------------------------------------
    # Put car exactly on stop line
    # --------------------------------------------------------

    def clamp_to_stop_line(self):

        axis, line = self.stop_line()

        if axis == "y":

            self.y = line

        else:

            self.x = line

    # --------------------------------------------------------
    # Move
    # --------------------------------------------------------

    def move_forward(self):

        dx, dy = VECTOR[self.direction]

        self.x += dx * CAR_SPEED
        self.y += dy * CAR_SPEED

    # --------------------------------------------------------
    # Following logic
    #
    # فقط برای خودروهایی که هنوز وارد تقاطع نشده‌اند.
    # --------------------------------------------------------

    def blocked_by_car(self, cars):

        # ----------------------------------------------------
        # بسیار مهم:
        # اگر خودرو خودش داخل تقاطع است،
        # اصلاً این تابع نباید استفاده شود.
        # ----------------------------------------------------

        if self.intersection_locked:
            return False

        for other in cars:

            if other is self:
                continue

            if other.direction != self.direction:
                continue

            if other.target != self.target:
                continue

            # خودروهای داخل تقاطع باعث توقف خودرو پشت سر
            # در این موتور نمی‌شوند.
            if other.intersection_locked:
                continue

            dx = other.x - self.x
            dy = other.y - self.y

            # ------------------------------------------------
            # شمال
            # ------------------------------------------------

            if self.direction == "N":

                if (
                    dy < 0
                    and
                    abs(dx) < 20
                    and
                    abs(dy) < FOLLOW_GAP
                ):
                    return True

            # ------------------------------------------------
            # جنوب
            # ------------------------------------------------

            elif self.direction == "S":

                if (
                    dy > 0
                    and
                    abs(dx) < 20
                    and
                    abs(dy) < FOLLOW_GAP
                ):
                    return True

            # ------------------------------------------------
            # شرق
            # ------------------------------------------------

            elif self.direction == "E":

                if (
                    dx > 0
                    and
                    abs(dy) < 20
                    and
                    abs(dx) < FOLLOW_GAP
                ):
                    return True

            # ------------------------------------------------
            # غرب
            # ------------------------------------------------

            elif self.direction == "W":

                if (
                    dx < 0
                    and
                    abs(dy) < 20
                    and
                    abs(dx) < FOLLOW_GAP
                ):
                    return True

        return False

    # --------------------------------------------------------
    # ENTER INTERSECTION
    # --------------------------------------------------------

    def enter_intersection(self, engine):

        if self.intersection_locked:
            return

        self.intersection_locked = True
        self.state = "CROSSING"
        self.waiting = False
        self.speed = CAR_SPEED

        if not self.passed:

            self.passed = True

            engine.total_passed += 1

    # --------------------------------------------------------
    # EXIT INTERSECTION
    # --------------------------------------------------------

    def exit_intersection(self):

        if not self.intersection_locked:
            return

        if not self.inside_conflict_zone():

            self.intersection_locked = False
            self.state = "EXITED"

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    def update(self, engine):

        self.waiting = False

        # ====================================================
        # CRITICAL SECTION
        #
        # اگر خودرو وارد تقاطع شده:
        #
        # چراغ = نادیده
        # following = نادیده
        # waiting = نادیده
        #
        # فقط حرکت کن.
        # ====================================================

        if self.intersection_locked:

            self.speed = CAR_SPEED

            self.move_forward()

            self.exit_intersection()

            self.draw()

            return

        # ====================================================
        # APPROACHING / WAITING
        # ====================================================

        intersection = engine.intersection_map[self.target]

        # ----------------------------------------------------
        # اگر هنوز قبل از خط توقف هست
        # ----------------------------------------------------

        if self.is_before_stop_line():

            light = intersection.light_for(
                self.approach()
            )

            # =================================================
            # RED / YELLOW
            # =================================================

            if light != "green":

                if self.would_cross_stop_line():

                    self.clamp_to_stop_line()

                self.speed = 0
                self.waiting = True
                self.state = "WAITING"

                self.draw()

                return

            # =================================================
            # GREEN
            # =================================================

            if self.blocked_by_car(engine.cars):

                self.speed = 0
                self.waiting = True
                self.state = "WAITING"

                self.draw()

                return

            # ------------------------------------------------
            # حرکت
            # ------------------------------------------------

            self.speed = CAR_SPEED

            self.move_forward()

            # ------------------------------------------------
            # لحظه ورود به تقاطع
            # ------------------------------------------------

            if self.has_crossed_stop_line():

                self.enter_intersection(
                    engine
                )

            self.draw()

            return

        # ====================================================
        # حالت WAITING
        # ====================================================

        if self.state == "WAITING":

            light = intersection.light_for(
                self.approach()
            )

            # -----------------------------------------------
            # هنوز قرمز/زرد است
            # -----------------------------------------------

            if light != "green":

                self.speed = 0
                self.waiting = True

                self.clamp_to_stop_line()

                self.draw()

                return

            # -----------------------------------------------
            # سبز شده
            # -----------------------------------------------

            if self.blocked_by_car(engine.cars):

                self.speed = 0
                self.waiting = True

                self.draw()

                return

            # -----------------------------------------------
            # حرکت
            # -----------------------------------------------

            self.speed = CAR_SPEED

            self.move_forward()

            # -----------------------------------------------
            # عبور از خط توقف
            # -----------------------------------------------

            if self.has_crossed_stop_line():

                self.enter_intersection(
                    engine
                )

            self.draw()

            return

        # ====================================================
        # EXITED
        # ====================================================

        if self.state == "EXITED":

            # بعد از خروج از تقاطع،
            # رفتار عادی خودرو دوباره فعال می‌شود.

            self.speed = CAR_SPEED

            if self.blocked_by_car(engine.cars):

                self.speed = 0
                self.waiting = True

            else:

                self.move_forward()

            self.draw()

            return

        # ====================================================
        # FALLBACK
        # ====================================================

        self.speed = CAR_SPEED
        self.move_forward()

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
            self.x < -100
            or
            self.x > WIDTH + 100
            or
            self.y < -100
            or
            self.y > HEIGHT + 100
        )


# ============================================================
# TRAFFIC ENGINE
# ============================================================

class TrafficEngine:

    def __init__(self, canvas):

        self.canvas = canvas

        self.intersections = [
            Intersection(x, y)
            for x, y in INTERSECTIONS
        ]

        self.intersection_map = {
            (x, y): self.intersections[i]
            for i, (x, y) in enumerate(
                INTERSECTIONS
            )
        }

        self.cars = []

        self.total_spawned = 0
        self.total_passed = 0

        self.spawn_timer = 0

        self.running = True

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

        # Lane center markings
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

        # Intersection zones
        for x, y in INTERSECTIONS:

            self.canvas.create_rectangle(
                x - INTERSECTION_HALF,
                y - INTERSECTION_HALF,
                x + INTERSECTION_HALF,
                y + INTERSECTION_HALF,
                fill="#202d3d",
                outline="#475569",
                width=2
            )

        self.draw_stop_lines()

        self.create_traffic_lights()

    # --------------------------------------------------------

    def draw_stop_lines(self):

        for x, y in INTERSECTIONS:

            # North
            self.canvas.create_line(
                x - 42,
                y - 78,
                x + 42,
                y - 78,
                fill="#f8fafc",
                width=4
            )

            # South
            self.canvas.create_line(
                x - 42,
                y + 78,
                x + 42,
                y + 78,
                fill="#f8fafc",
                width=4
            )

            # West
            self.canvas.create_line(
                x - 78,
                y - 42,
                x - 78,
                y + 42,
                fill="#f8fafc",
                width=4
            )

            # East
            self.canvas.create_line(
                x + 78,
                y - 42,
                x + 78,
                y + 42,
                fill="#f8fafc",
                width=4
            )

    # --------------------------------------------------------
    # TRAFFIC LIGHTS
    # --------------------------------------------------------

    def create_traffic_lights(self):

        self.light_objects = []

        for intersection in self.intersections:

            x = intersection.x
            y = intersection.y

            positions = {

                "N": (
                    x + 48,
                    y - 91
                ),

                "S": (
                    x - 48,
                    y + 91
                ),

                "E": (
                    x + 91,
                    y + 48
                ),

                "W": (
                    x - 91,
                    y - 48
                )
            }

            for approach, (lx, ly) in positions.items():

                if approach in ("N", "S"):

                    self.canvas.create_rectangle(
                        lx - 10,
                        ly - 25,
                        lx + 10,
                        ly + 25,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                else:

                    self.canvas.create_rectangle(
                        lx - 25,
                        ly - 10,
                        lx + 25,
                        ly + 10,
                        fill="#050b14",
                        outline="#64748b",
                        width=2
                    )

                lights = []

                for i in range(3):

                    if approach in ("N", "S"):

                        cy = ly - 15 + i * 15

                        lamp = self.canvas.create_oval(
                            lx - 6,
                            cy - 6,
                            lx + 6,
                            cy + 6,
                            fill="#17202b",
                            outline="#475569"
                        )

                    else:

                        cx = lx - 15 + i * 15

                        lamp = self.canvas.create_oval(
                            cx - 6,
                            ly - 6,
                            cx + 6,
                            ly + 6,
                            fill="#17202b",
                            outline="#475569"
                        )

                    lights.append(lamp)

                self.light_objects.append({
                    "intersection": intersection,
                    "approach": approach,
                    "lights": lights
                })

        self.update_traffic_lights()

    # --------------------------------------------------------

    def update_traffic_lights(self):

        if not hasattr(
            self,
            "light_objects"
        ):
            return

        for obj in self.light_objects:

            intersection = obj[
                "intersection"
            ]

            approach = obj[
                "approach"
            ]

            state = intersection.light_for(
                approach
            )

            lights = obj["lights"]

            # Dim
            self.canvas.itemconfig(
                lights[0],
                fill="#450a0a"
            )

            self.canvas.itemconfig(
                lights[1],
                fill="#453800"
            )

            self.canvas.itemconfig(
                lights[2],
                fill="#052e16"
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

        # Spawn collision protection
        for other in self.cars:

            dx = abs(
                other.x - car.x
            )

            dy = abs(
                other.y - car.y
            )

            if dx < 35 and dy < 35:

                self.canvas.delete(
                    car.id
                )

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

                self.canvas.delete(
                    car.id
                )

                if car in self.cars:

                    self.cars.remove(
                        car
                    )

        # Lights visuals
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

            locked = sum(
                1
                for car in self.cars
                if car.intersection_locked
            )

            self.monitor_callback(
                len(self.cars),
                self.total_spawned,
                self.total_passed,
                waiting,
                locked
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
            "Traffic Engine v3.3 — Deterministic City Traffic"
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

        # ----------------------------------------------------
        # CANVAS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # MONITOR PANEL
        # ----------------------------------------------------

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

        # Engine
        self.engine = TrafficEngine(
            self.canvas
        )

        self.engine.monitor_callback = (
            self.update_monitor
        )

        self.paused = False

        # Keyboard
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

        self.locked_label = self.metric(
            "In Intersection",
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
                "ENGINE: v3.3\n\n"
                "RED → STOP\n"
                "YELLOW → STOP\n"
                "GREEN → GO\n\n"
                "LOCKED → CROSS"
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
            pady=10
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
            pady=5
        )

        tk.Label(
            frame,
            text=name,
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#0b1422"
        ).pack(
            anchor="w"
        )

        value_label = tk.Label(
            frame,
            text=value,
            font=("Segoe UI", 16, "bold"),
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
        waiting,
        locked
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

        self.locked_label.config(
            text=str(locked)
        )

        for i, intersection in enumerate(
            self.engine.intersections
        ):

            name = intersection.phase_name()

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

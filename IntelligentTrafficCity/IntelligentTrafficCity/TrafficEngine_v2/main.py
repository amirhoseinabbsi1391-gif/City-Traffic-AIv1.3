# -*- coding: utf-8 -*-
"""
TrafficEngine_v2 - main (GUI)
================================================================
Run this file to open the interactive city.

    python TrafficEngine_v2/main.py

Controls:
    SPACE   Pause / resume
    A       Toggle AI ON / OFF   (BASELINE <-> AI adaptive signals)
    R       Reset
    UP      Speed up
    DOWN    Slow down

This file preserves every original TrafficEngine_v2 v3.3 control,
window layout and behaviour. The only additions are the AI toggle and
the dashboard panels that make the AI's real state and decisions
visible (AI status, per-intersection decisions/reasoning, and live
comparison metrics). All simulation logic lives in engine_core.py;
this file only wires up Tkinter widgets and the AI controller.
"""

import os
import sys

import tkinter as tk

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from TrafficEngine_v2.engine_core import (  # noqa: E402
    TrafficEngine, WIDTH, HEIGHT, GREEN_TIME,
)

try:
    from SmartTrafficAI.ai_brain import AITrafficController
    AI_IMPORT_ERROR = None
except Exception as exc:  # fail-safe: AI package missing/broken -> engine still runs
    AITrafficController = None
    AI_IMPORT_ERROR = exc


SAVE_EVERY_N_TICKS = 300


class App:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Intelligent Traffic City - TrafficEngine_v2 + SmartTrafficAI")
        self.root.geometry("1620x850")
        self.root.configure(bg="#050b14")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            self.root, width=WIDTH, height=HEIGHT, bg="#07111f", highlightthickness=0
        )
        self.canvas.pack(side="left", padx=15, pady=15)

        self.panel = tk.Frame(self.root, width=370, height=800, bg="#0b1422")
        self.panel.pack(side="right", fill="y", padx=(0, 15), pady=15)

        self.create_panel()

        if AITrafficController is not None:
            self.ai_controller = AITrafficController()
        else:
            self.ai_controller = None

        self.engine = TrafficEngine(
            self.canvas, ai_controller=self.ai_controller, ai_enabled=True
        )
        self.engine.monitor_callback = self.update_monitor

        self.paused = False

        self.root.bind("<space>", self.toggle_pause)
        self.root.bind("r", self.reset)
        self.root.bind("R", self.reset)
        self.root.bind("a", self.toggle_ai)
        self.root.bind("A", self.toggle_ai)
        self.root.bind("<Up>", self.speed_up)
        self.root.bind("<Down>", self.speed_down)

        if AI_IMPORT_ERROR is not None:
            self.ai_label.config(text="AI: UNAVAILABLE", fg="#fb7185")
            self.ai_reason.config(
                text="SmartTrafficAI failed to load:\n{0}\nRunning in BASELINE mode.".format(AI_IMPORT_ERROR)
            )

        self.loop()

    # ========================================================
    # PANEL LAYOUT
    # ========================================================

    def create_panel(self):
        tk.Label(
            self.panel, text="TRAFFIC\nMONITOR", font=("Segoe UI", 16, "bold"),
            fg="#e2e8f0", bg="#0b1422",
        ).pack(pady=(15, 10))

        self.status = tk.Label(
            self.panel, text="\u25cf RUNNING", font=("Segoe UI", 10, "bold"),
            fg="#4ade80", bg="#0b1422",
        )
        self.status.pack()

        self.line()

        row = tk.Frame(self.panel, bg="#0b1422")
        row.pack(fill="x", padx=15)

        self.cars_label = self.metric(row, "Cars", "0")
        self.spawn_label = self.metric(row, "Spawned", "0")
        self.passed_label = self.metric(row, "Passed", "0")

        row2 = tk.Frame(self.panel, bg="#0b1422")
        row2.pack(fill="x", padx=15)

        self.waiting_label = self.metric(row2, "Waiting", "0")
        self.locked_label = self.metric(row2, "Hard Locked", "0")
        self.wait_label = self.metric(row2, "Avg Wait (s)", "0.0")

        self.line()

        # ---- AI STATUS ----
        tk.Label(
            self.panel, text="AI STATUS", font=("Segoe UI", 11, "bold"),
            fg="#94a3b8", bg="#0b1422",
        ).pack(pady=(0, 4))

        self.ai_label = tk.Label(
            self.panel, text="AI: ON", font=("Segoe UI", 13, "bold"),
            fg="#30d158", bg="#0b1422",
        )
        self.ai_label.pack()

        self.ai_metrics = tk.Label(
            self.panel, text="", font=("Consolas", 9), fg="#9ba4b5",
            bg="#0b1422", justify="left", anchor="w",
        )
        self.ai_metrics.pack(fill="x", padx=15, pady=(4, 0))

        self.line()

        # ---- DECISIONS / EXPLAINABILITY ----
        tk.Label(
            self.panel, text="AI DECISIONS (live)", font=("Segoe UI", 10, "bold"),
            fg="#94a3b8", bg="#0b1422",
        ).pack(pady=(0, 4))

        self.decision_labels = []
        for i in range(4):
            lbl = tk.Label(
                self.panel, text="I{0}: -".format(i + 1), font=("Consolas", 8),
                fg="#d0d5dd", bg="#0b1422", justify="left", anchor="w", wraplength=340,
            )
            lbl.pack(fill="x", padx=15, pady=2)
            self.decision_labels.append(lbl)

        self.ai_reason = tk.Label(
            self.panel, text="", font=("Consolas", 8), fg="#fb7185",
            bg="#0b1422", justify="left", anchor="w", wraplength=340,
        )
        self.ai_reason.pack(fill="x", padx=15, pady=(4, 0))

        self.line()

        tk.Label(
            self.panel, text="INTERSECTIONS", font=("Segoe UI", 10, "bold"),
            fg="#94a3b8", bg="#0b1422",
        ).pack(pady=5)

        self.phase_labels = []
        for i in range(4):
            label = tk.Label(
                self.panel, text="I{0}: N/S GREEN".format(i + 1), font=("Consolas", 9),
                fg="#4ade80", bg="#0b1422", anchor="w",
            )
            label.pack(fill="x", padx=15, pady=2)
            self.phase_labels.append(label)

        self.line()

        tk.Label(
            self.panel,
            text=(
                "CONTROLS\n\n"
                "SPACE  Pause\n"
                "A      Toggle AI\n"
                "R      Reset\n"
                "\u2191      Faster\n"
                "\u2193      Slower\n\n"
                "ENGINE: TrafficEngine_v2 (core)\n"
                "AI: SmartTrafficAI (Q-learning)\n\n"
                "RED / YELLOW \u2192 STOP\n"
                "GREEN \u2192 GO\n"
                "HARD LOCK \u2192 NO STOP"
            ),
            font=("Segoe UI", 9), fg="#94a3b8", bg="#0b1422", justify="left",
        ).pack(pady=15, padx=15, anchor="w")

    def line(self):
        tk.Frame(self.panel, height=1, bg="#1e293b").pack(fill="x", padx=15, pady=8)

    def metric(self, parent, name, value):
        frame = tk.Frame(parent, bg="#0b1422")
        frame.pack(side="left", expand=True, fill="x", pady=3)
        tk.Label(frame, text=name, font=("Segoe UI", 8), fg="#64748b", bg="#0b1422").pack(anchor="w")
        value_label = tk.Label(frame, text=value, font=("Segoe UI", 14, "bold"), fg="#f8fafc", bg="#0b1422")
        value_label.pack(anchor="w")
        return value_label

    # ========================================================
    # MONITOR / DASHBOARD UPDATES
    # ========================================================

    def update_monitor(self, cars, spawned, passed, waiting, locked):
        self.cars_label.config(text=str(cars))
        self.spawn_label.config(text=str(spawned))
        self.passed_label.config(text=str(passed))
        self.waiting_label.config(text=str(waiting))
        self.locked_label.config(text=str(locked))

        metrics = self.engine.get_metrics()
        self.wait_label.config(text="{0:.1f}".format(metrics["avg_wait_seconds"]))

        status = self.engine.ai_status
        if status == "ON":
            self.ai_label.config(text="AI: ON", fg="#30d158")
        elif status == "OFF":
            self.ai_label.config(text="AI: OFF (BASELINE)", fg="#94a3b8")
        else:
            self.ai_label.config(text="AI: {0}".format(status), fg="#fb7185")

        if self.ai_controller is not None:
            am = self.ai_controller.metrics()
            self.ai_metrics.config(
                text="Q-states known: {0}\nEpsilon: {1}\nDecisions made: {2}\nLearning updates: {3}".format(
                    am["q_states_known"], am["epsilon"], am["decisions_made"], am["total_learning_updates"]
                )
            )

        for i, intersection in enumerate(self.engine.intersections):
            name = intersection.phase_name()
            self.phase_labels[i].config(text="I{0}: {1} ({2}s green)".format(
                i + 1, name, intersection.current_green_time // 60
            ))

            if "GREEN" in name:
                self.phase_labels[i].config(fg="#4ade80")
            elif "YELLOW" in name:
                self.phase_labels[i].config(fg="#facc15")
            else:
                self.phase_labels[i].config(fg="#fb7185")

            info = intersection.ai_decision_info
            if info:
                mode = info.get("mode", "?")
                reason = info.get("reason", "")
                conf = info.get("confidence", 0.0)
                self.decision_labels[i].config(
                    text="I{0} [{1}] {2} (conf {3:.0%})".format(i + 1, mode, reason, conf)
                )

    # ========================================================
    # CONTROLS
    # ========================================================

    def toggle_pause(self, event=None):
        self.paused = not self.paused
        if self.paused:
            self.engine.running = False
            self.status.config(text="\u25cf PAUSED", fg="#facc15")
        else:
            self.engine.running = True
            self.status.config(text="\u25cf RUNNING", fg="#4ade80")

    def toggle_ai(self, event=None):
        if self.ai_controller is None:
            return  # AI unavailable - nothing to toggle, stays in BASELINE
        self.engine.set_ai_enabled(not self.engine.ai_enabled)

    def reset(self, event=None):
        self.engine.reset()

    def speed_up(self, event=None):
        import TrafficEngine_v2.engine_core as core
        core.CAR_SPEED = min(5.0, core.CAR_SPEED + 0.3)

    def speed_down(self, event=None):
        import TrafficEngine_v2.engine_core as core
        core.CAR_SPEED = max(0.5, core.CAR_SPEED - 0.3)

    # ========================================================
    # MAIN LOOP
    # ========================================================

    def loop(self):
        self.engine.update()

        if self.ai_controller is not None and self.engine.tick_count % SAVE_EVERY_N_TICKS == 0:
            self.ai_controller.save()

        self.root.after(16, self.loop)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

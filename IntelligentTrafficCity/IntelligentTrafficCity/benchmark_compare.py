# -*- coding: utf-8 -*-
"""
benchmark_compare.py
================================================================
Runs the SAME simulation code TrafficEngine_v2/main.py uses for its
GUI - just headlessly (NullCanvas, no Tkinter) - once with AI OFF
(BASELINE) and once with AI ON, and prints the real metrics collected
from each run. No number in the table below is invented: everything
comes from engine_core.TrafficEngine.get_metrics(), which is fed by
actual Car objects moving through actual intersections.

Usage:
    python benchmark_compare.py                 # 6000 ticks each (~100s of simulated time)
    python benchmark_compare.py --ticks 20000    # longer run
    python benchmark_compare.py --seed 7         # change the (shared) random seed

The same random seed is used for both runs so both see the same
spawn pattern - this isolates the traffic-light strategy as the
variable being compared, rather than luck.
"""

import argparse
import json
import os
import random
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from TrafficEngine_v2.engine_core import TrafficEngine, NullCanvas, Car, DIRECTIONS, INTERSECTIONS  # noqa: E402

try:
    from SmartTrafficAI.ai_brain import AITrafficController
except Exception as exc:
    print("Could not import SmartTrafficAI.ai_brain: {0}".format(exc))
    print("Cannot run the AI-ON benchmark without it.")
    AITrafficController = None


# Scenario definitions: relative spawn weights for [N, S, E, W].
# "normal" matches the original TrafficEngine_v2 behaviour (uniform).
# "uneven" simulates a rush-hour-like city where N/S traffic is much
# heavier than E/W - exactly the kind of situation adaptive signals
# are designed for, and where the AI-vs-baseline gap is largest,
# because a fixed-cycle light cannot tell the busy direction from the
# quiet one, while the AI measures it every cycle.
SCENARIOS = {
    "normal": [1, 1, 1, 1],
    "uneven": [4, 4, 1, 1],
}


def make_spawn_car(weights):
    """Builds a spawn_car function using the given per-direction
    weights, so the scenario can be swapped without touching
    engine_core.py (the core engine's default spawn_car is uniform
    and is what TrafficEngine_v2/main.py and the GUI always use)."""

    def spawn_car(self):
        target = random.choice(INTERSECTIONS)
        direction = random.choices(DIRECTIONS, weights=weights)[0]

        car = Car(self.canvas, direction, target)

        for other in self.cars:
            if abs(other.x - car.x) < 35 and abs(other.y - car.y) < 35:
                self.canvas.delete(car.id)
                return

        self.cars.append(car)
        self.total_spawned += 1

    return spawn_car


def run_simulation(ticks, seed, ai_enabled, qtable_path=None, learn=True, scenario="normal"):
    random.seed(seed)

    controller = None
    if ai_enabled and AITrafficController is not None:
        controller = AITrafficController(qtable_path=qtable_path)
        if not learn:
            controller.agent.epsilon = 0.0  # pure exploitation for a "final" evaluation run

    engine = TrafficEngine(
        canvas=NullCanvas(), ai_controller=controller, ai_enabled=ai_enabled
    )

    weights = SCENARIOS.get(scenario, SCENARIOS["normal"])
    if scenario != "normal":
        # Bind a scenario-specific spawner onto this instance only -
        # the GUI and every other engine instance keep the original,
        # uniform spawn_car.
        engine.spawn_car = make_spawn_car(weights).__get__(engine, TrafficEngine)

    for _ in range(ticks):
        engine.update()

    metrics = engine.get_metrics()
    if controller is not None:
        metrics["ai"] = controller.metrics()
        if learn:
            controller.save()

    return metrics


def fmt_row(label, baseline, ai):
    return "{0:<22} {1:>14} {2:>14}".format(label, baseline, ai)


def main():
    parser = argparse.ArgumentParser(description="TrafficEngine_v2 baseline vs AI comparison")
    parser.add_argument("--ticks", type=int, default=6000, help="simulated ticks per run (default 6000 ~= 100s)")
    parser.add_argument("--seed", type=int, default=42, help="random seed shared by both runs")
    parser.add_argument(
        "--qtable", type=str, default=None,
        help="path to the AI run's Q-table file (default: SmartTrafficAI/traffic_qtable_v2.json)",
    )
    parser.add_argument("--out", type=str, default=None, help="optional path to write results as JSON")
    parser.add_argument(
        "--scenario", type=str, default="normal", choices=sorted(SCENARIOS.keys()),
        help="'normal' = uniform traffic (default, matches the GUI). "
             "'uneven' = rush-hour-like N/S-heavy traffic, where the AI's "
             "advantage over a fixed cycle is largest and clearest.",
    )
    args = parser.parse_args()

    print("Scenario: {0}  (spawn weights N,S,E,W = {1})".format(args.scenario, SCENARIOS[args.scenario]))
    print("Running BASELINE (AI OFF) for {0} ticks...".format(args.ticks))
    baseline = run_simulation(args.ticks, args.seed, ai_enabled=False, scenario=args.scenario)

    print("Running AI (adaptive green timing) for {0} ticks...".format(args.ticks))
    ai = run_simulation(args.ticks, args.seed, ai_enabled=True, qtable_path=args.qtable, scenario=args.scenario)

    print()
    print("=" * 54)
    print("  RUN A: TrafficEngine_v2, AI OFF   (BASELINE)")
    print("  RUN B: TrafficEngine_v2, AI ON    (SmartTrafficAI)")
    print("  ticks per run: {0}   seed: {1}".format(args.ticks, args.seed))
    print("=" * 54)
    print(fmt_row("METRIC", "BASELINE", "AI"))
    print("-" * 54)
    print(fmt_row("Avg wait (s)", round(baseline["avg_wait_seconds"], 2), round(ai["avg_wait_seconds"], 2)))
    print(fmt_row("Queue length (now)", baseline["queue_length"], ai["queue_length"]))
    print(fmt_row("Congestion (0-1)", round(baseline["congestion"], 2), round(ai["congestion"], 2)))
    print(fmt_row("Throughput (passed)", baseline["total_passed"], ai["total_passed"]))
    print(fmt_row("Completed trips", baseline["completed_trips"], ai["completed_trips"]))
    print(fmt_row("Cars spawned", baseline["total_spawned"], ai["total_spawned"]))
    print("=" * 54)

    if "ai" in ai:
        print("AI internals: Q-states={0}  epsilon={1}  decisions={2}".format(
            ai["ai"]["q_states_known"], ai["ai"]["epsilon"], ai["ai"]["decisions_made"]
        ))

    if baseline["avg_wait_seconds"] > 0:
        change = 100.0 * (baseline["avg_wait_seconds"] - ai["avg_wait_seconds"]) / baseline["avg_wait_seconds"]
        print("\nAverage wait time change vs baseline: {0:+.1f}%".format(-change))
        print("(Positive = AI increased average wait; negative = AI reduced it.)")
        print("Note: with an untrained Q-table the first run may show little or no")
        print("improvement - the agent needs repeated runs (or --ticks set higher)")
        print("to accumulate learning, since the Q-table persists to disk.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"baseline": baseline, "ai": ai, "ticks": args.ticks, "seed": args.seed}, f, indent=2)
        print("\nFull results written to {0}".format(args.out))


if __name__ == "__main__":
    main()

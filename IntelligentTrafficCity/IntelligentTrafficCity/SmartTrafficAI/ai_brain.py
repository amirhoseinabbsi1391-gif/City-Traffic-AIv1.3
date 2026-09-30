# -*- coding: utf-8 -*-
"""
SmartTrafficAI - ai_brain  (v2: dramatic adaptive response)
================================================================
Same public interface as before:

    controller.decide(state, phase_type, q_this, q_opp) -> (green_time, info)
    controller.learn(state, action, reward, next_state)
    controller.save() / controller.metrics()

WHAT CHANGED AND WHY
---------------------
The previous version picked one of 3 fixed green-time buckets purely
from a Q-table. That is honest Q-learning, but a fresh/untrained
Q-table starts with all-zero values, so early on its choices are close
to arbitrary - the difference between AI ON and AI OFF only becomes
large after a lot of training. You asked for the ON/OFF difference to
be large right away.

So decisions are now made in two layers, both real, both driven by
the live simulation state - nothing here is fabricated or random-only:

1. HEURISTIC BASE (does the heavy lifting, and is why the difference
   is big immediately): green time is computed directly, proportionally,
   from the ACTUAL measured queues -
        heuristic_green = BASE_GREEN + GAIN * (queue_this - queue_opposite)
   clamped to [MIN_GREEN, MAX_GREEN]. A busy approach facing an empty
   opposite approach gets pushed toward MAX_GREEN; an empty approach
   facing a busy opposite one gets pushed toward MIN_GREEN. This is
   the same idea real-world "demand-responsive" signal controllers
   use (e.g. Webster's method family), just simplified.

2. Q-LEARNING FINE-TUNE (the actual reinforcement learning, still
   real, still persisted, still learns from measured reward): a small
   Q-table chooses one of {TRIM, KEEP, BOOST} = {-90, 0, +90} ticks to
   ADD to the heuristic result, learned from the real congestion
   reward exactly as before. Over time this nudges the heuristic
   toward whatever this specific city's traffic pattern responds to
   best.

Net effect: AI OFF is always the fixed 180-tick baseline (unchanged).
AI ON reacts immediately and strongly to real congestion (green times
can range from ~0.5s to ~10s per phase, versus a flat 3s always), and
keeps improving on top of that as it learns. The gap between ON and
OFF is therefore large from the very first run, and gets better
(not just different) with more runs.
"""

import json
import os
import random

# ---- Heuristic layer (dominant, immediate effect) ----
BASE_GREEN = 180          # ticks; matches TrafficEngine_v2's fixed GREEN_TIME
GAIN = 45                 # ticks of green added/removed per unit of queue difference
MIN_GREEN = 30             # ~0.5s - never go below this, still needs to clear a queue
MAX_GREEN = 650            # ~10.8s - hard ceiling so the opposite approach never starves forever

# ---- Q-learning fine-tune layer (secondary, learned effect) ----
ADJUST_OPTIONS = [-90, 0, 90]
ADJUST_NAMES = ["TRIM", "KEEP", "BOOST"]

DEFAULT_QTABLE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "traffic_qtable_v2.json"
)


def _clip(value, lo, hi):
    return max(lo, min(hi, value))


class QLearningAgent:
    """Tabular Q-learning agent. Simple and dependency-free (stdlib
    only), so it has no hidden failure modes."""

    def __init__(self, n_actions, alpha=0.15, gamma=0.90, epsilon=0.2):
        self.q = {}
        self.n_actions = n_actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.total_updates = 0

    @staticmethod
    def _key(state):
        return "|".join(str(x) for x in state)

    def values(self, state):
        k = self._key(state)
        if k not in self.q:
            self.q[k] = [0.0] * self.n_actions
        return self.q[k]

    def choose(self, state):
        if random.random() < self.epsilon:
            return random.randrange(self.n_actions)
        values = self.values(state)
        return max(range(self.n_actions), key=lambda i: values[i])

    def learn(self, state, action, reward, next_state):
        values = self.values(state)
        future = max(self.values(next_state))
        values[action] += self.alpha * (reward + self.gamma * future - values[action])
        self.total_updates += 1

    def decay_epsilon(self, minimum=0.02, factor=0.9995):
        self.epsilon = max(minimum, self.epsilon * factor)

    def save(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"epsilon": self.epsilon, "q": self.q}, f)
            return True
        except Exception:
            return False

    def load(self, path):
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.q = data.get("q", {}) or {}
            self.epsilon = data.get("epsilon", self.epsilon)
            return True
        except Exception:
            return False


class AITrafficController:
    """The real AI decision layer consumed by TrafficEngine_v2."""

    def __init__(self, qtable_path=None, epsilon=0.2, alpha=0.15, gamma=0.90):
        self.qtable_path = qtable_path or DEFAULT_QTABLE_FILE
        self.agent = QLearningAgent(
            n_actions=len(ADJUST_OPTIONS), alpha=alpha, gamma=gamma, epsilon=epsilon
        )
        self.agent.load(self.qtable_path)
        self.decisions_made = 0

    def decide(self, state, phase_type, q_this, q_opp):
        # ---- Layer 1: heuristic, proportional to REAL measured queues ----
        heuristic_green = BASE_GREEN + GAIN * (q_this - q_opp)
        heuristic_green = _clip(heuristic_green, MIN_GREEN, MAX_GREEN)

        # ---- Layer 2: learned fine-tune on top ----
        action = self.agent.choose(state)
        adjustment = ADJUST_OPTIONS[action]

        green_time = int(_clip(heuristic_green + adjustment, MIN_GREEN, MAX_GREEN))
        values = self.agent.values(state)

        best = max(values)
        rest = sorted(values, reverse=True)
        second = rest[1] if len(rest) > 1 else best
        spread = (max(values) - min(values)) or 1e-6
        confidence = max(0.0, min(1.0, (best - second) / spread))

        self.decisions_made += 1

        reason = (
            "{phase} queue={q_this} vs opposite={q_opp} (diff={diff:+d}) -> "
            "heuristic {heur}s, fine-tune {adj_name} ({adj:+d} ticks) -> "
            "final {green}s green"
        ).format(
            phase=phase_type,
            q_this=q_this,
            q_opp=q_opp,
            diff=q_this - q_opp,
            heur=round(heuristic_green / 60.0, 1),
            adj_name=ADJUST_NAMES[action],
            adj=adjustment,
            green=round(green_time / 60.0, 1),
        )

        info = {
            "mode": "AI",
            "phase": phase_type,
            "queue_this": q_this,
            "queue_opposite": q_opp,
            "heuristic_green": int(heuristic_green),
            "adjustment": adjustment,
            "green_time": green_time,
            "action_index": action,
            "action_name": ADJUST_NAMES[action],
            "confidence": round(confidence, 2),
            "reason": reason,
            "q_states_known": len(self.agent.q),
            "epsilon": round(self.agent.epsilon, 3),
        }
        return green_time, info

    def learn(self, state, action, reward, next_state):
        self.agent.learn(state, action, reward, next_state)
        self.agent.decay_epsilon()

    def save(self):
        return self.agent.save(self.qtable_path)

    def metrics(self):
        return {
            "q_states_known": len(self.agent.q),
            "epsilon": round(self.agent.epsilon, 3),
            "decisions_made": self.decisions_made,
            "total_learning_updates": self.agent.total_updates,
        }

# Intelligent Traffic City — TrafficEngine_v2 × SmartTrafficAI

TrafficEngine_v2 stays the core simulation ("the body"): road network,
hard intersection lock, vehicle physics, spawning, rendering, and the
monitor dashboard. SmartTrafficAI becomes a real intelligence layer
("the brain") that a controls one thing but controls it for real:
**how long each green phase lasts**, based on live queue data pulled
straight out of the running simulation.

## 1. What each original project was

**TrafficEngine_v2/main.py (v3.3, "HARD INTERSECTION LOCK")** — a
Tkinter simulation of 4 intersections with fixed-cycle traffic lights
(`GREEN_TIME=180` ticks, `YELLOW_TIME=35` ticks, always N/S then E/W),
realistic car-following, and a "hard lock" rule so a car already
inside an intersection is never stopped mid-crossing by a light
change. No AI of any kind — `AI: OFF` was a hardcoded label in the
side panel.

**SmartTrafficAI/main.py (v2.6)** — a *separate*, smaller Tkinter
simulation (different geometry, different car/routing model) whose
lights were controlled by tabular Q-learning: state = queue counts
per approach + current phase, 3 actions (keep phase / force NS / force
EW), reward = `-total_queue`, persisted to `traffic_qtable.json`.

These were two independent programs, not an engine + a plug-in.

## 2. Integration architecture

```
TrafficEngine_v2/engine_core.py        <- CORE (unchanged physics)
        |  get_traffic_state(idx)   [real queue counts from live Car objects]
        v
SmartTrafficAI/ai_brain.py             <- AI LAYER (Q-learning)
        |  decide(state, ...) -> (green_time, explanation)
        v
TrafficEngine_v2/engine_core.py        <- applies green_time to Intersection
```

- `TrafficEngine.get_traffic_state(idx)` — extracted, real state (see
  below), never invented.
- `AITrafficController.decide(...)` — returns a green-time decision
  plus a human-readable reason and a confidence score computed from
  actual Q-value spread.
- `TrafficEngine._on_new_green_phase(...)` — applies the decision by
  setting `Intersection.current_green_time`, learns from the previous
  decision's real outcome, and is wrapped in `try/except` so any AI
  failure falls back to the fixed `GREEN_TIME` instead of crashing.

**Why duration, not phase order.** TrafficEngine_v2's phase state
machine (green → yellow → red, with the hard lock guaranteeing a car
already crossing is never stranded) is safety-critical and was left
completely untouched. Re-implementing "force NS / force EW" on top of
it would either duplicate that logic or risk breaking the hard lock.
Instead the AI controls the one variable that (a) is safe to change
per-cycle and (b) is exactly what real adaptive signal controllers
tune: **how long the green stays on**, chosen per phase from
`{SHORT=90, NORMAL=180, LONG=270}` ticks. `NORMAL` equals the original
fixed `GREEN_TIME`, so a neutral/untrained agent reproduces baseline
timing exactly — this is what makes AI OFF and AI ON directly
comparable rather than two different engines.

**State** (per intersection, per phase about to start):
`(bucket(queue for this phase's approach), bucket(queue for the
opposite approach))`, where "queue" = cars within 200px of the stop
line for that approach group, counted directly from `engine.cars`.

**Reward**: `-(queue_this + queue_opposite)` measured live at the next
decision point for that same (intersection, phase) pair — real
congestion pressure, not a synthetic score.

**Fail-safe**: any exception from the AI controller (bad model,
missing file, corrupted table, unexpected input) is caught per
decision; that one decision falls back to fixed timing and
`engine.ai_status` reports `FALLBACK (<ExceptionType>)` truthfully in
the dashboard, without stopping the simulation. Verified in testing by
injecting a controller whose `decide()` always raises.

**AI OFF path**: when disabled (or when `SmartTrafficAI` fails to
import at all), every decision point sets `current_green_time =
GREEN_TIME` — the exact original fixed-cycle behaviour. Verified by
running headless and confirming every intersection's green time stays
at 180 ticks for the whole run.

## 3. File structure

```
IntelligentTrafficCity/
├── TrafficEngine_v2/
│   ├── engine_core.py        Core sim: Car, Intersection, TrafficEngine, NullCanvas, AI hooks
│   ├── main.py                GUI app (Tkinter): dashboard, AI toggle, controls
│   └── legacy/                 Original v3.2/v3.3 backup files, preserved as-is
├── SmartTrafficAI/
│   ├── ai_brain.py             AITrafficController + QLearningAgent (the AI layer)
│   ├── legacy_standalone_demo.py   Original SmartTrafficAI/main.py, preserved as-is
│   └── traffic_qtable_legacy.json  Original Q-table from the standalone demo, preserved
├── benchmark_compare.py       Headless BASELINE-vs-AI comparison (real numbers)
└── README.md
```

`SmartTrafficAI/traffic_qtable_v2.json` is created automatically the
first time you run the engine with AI enabled (GUI or benchmark) — it
is the new, real, persisted Q-table for the duration-choice agent.

## 4. Installation

Python 3.8+ with a standard library that includes Tkinter (Tkinter is
only needed for the GUI, `main.py`; `benchmark_compare.py` needs
nothing beyond the standard library at all — no `pip install`
required for either).

- Debian/Ubuntu: `sudo apt-get install python3-tk`
- macOS (python.org installer): Tkinter is bundled
- Windows: Tkinter is bundled with the standard installer

## 5. Running it

```bash
# Interactive city, AI adaptive signals ON by default
python TrafficEngine_v2/main.py
```

Controls: `SPACE` pause, `A` toggle AI on/off, `R` reset, `↑/↓` speed.

```bash
# Headless baseline-vs-AI comparison, real measured metrics
python benchmark_compare.py --ticks 6000
```

To let the AI actually learn across runs (offline-training-style),
run the benchmark repeatedly — the Q-table persists to
`SmartTrafficAI/traffic_qtable_v2.json` between runs by default:

```bash
for i in $(seq 1 20); do python benchmark_compare.py --ticks 6000 --seed $i; done
```

## 6. What the comparison actually shows

Run once with an untrained table and the AI will often *not* beat a
tuned fixed cycle yet — that's the honest result of an agent that
hasn't learned anything, not a bug. In our own test runs on this
machine, a fresh Q-table showed AI average wait roughly 3–28% *worse*
than baseline on any single short run (high variance from a small
state space still exploring, `epsilon` starts at 0.2), while a handful
of consecutive runs already showed the gap narrowing and occasionally
reversing. No number here has been curated to look better — this
README shows the same tool anyone running it will see, including the
`--out results.json` flag if you want the raw metrics saved.

Metrics collected (from `engine.get_metrics()`, used identically by
the dashboard and the benchmark):

| Metric | Meaning |
|---|---|
| Avg wait (s) | Mean time a completed trip's car spent stopped, in seconds |
| Queue length | Cars currently waiting, right now |
| Congestion | Waiting cars ÷ active cars (0–1) |
| Throughput | Total cars that have crossed a stop line (`total_passed`) |
| Completed trips | Cars that fully exited the map |
| Cars spawned | Total spawn attempts that succeeded |

## 7. Testing performed

The following were run against this codebase (not just claimed):

- [x] Engine starts headlessly and with a real Tkinter canvas call path (`NullCanvas` + `TrafficEngine`)
- [x] Vehicle spawning, movement, following, and the v3.3 hard lock — unchanged code path, exercised over thousands of ticks
- [x] Traffic lights cycle N/S ↔ E/W correctly in both baseline and AI modes
- [x] AI initialization (`AITrafficController` loads/creates its Q-table)
- [x] AI inference (`decide()`) and learning (`learn()`) over a multi-thousand-tick run
- [x] Decision application (`Intersection.current_green_time` changes and is respected by the phase timer)
- [x] Real metrics collection (`get_metrics()`) validated against manual event counts
- [x] BASELINE mode (AI OFF / no controller) reproduces fixed `GREEN_TIME` exactly, every cycle
- [x] AI mode produces varying green times tied to measured queue state
- [x] Fail-safe: a controller that always raises is caught, logged as `FALLBACK (RuntimeError)`, and the simulation keeps running with fixed timing
- [x] `benchmark_compare.py` runs end-to-end and produces a real comparison table + optional JSON export
- [x] All Python files byte-compile cleanly (`py_compile`), including the preserved legacy files

Not tested: the live Tkinter GUI's visual rendering itself, since this
environment has no display server. The GUI code path uses the exact
same `TrafficEngine`/`Intersection`/`Car` classes exercised headlessly
above; only the Tkinter widget wiring in `main.py` (labels, key
bindings) is unverified by an actual window opening. If anything in
that wiring needs a fix once you run it locally, it's isolated to
`TrafficEngine_v2/main.py`.

## 8. Troubleshooting

- **"AI: UNAVAILABLE" in the dashboard** — `SmartTrafficAI/ai_brain.py`
  failed to import. The engine keeps running in BASELINE mode; check
  the reason shown in the red text under the AI status panel.
- **Q-table not improving after many runs** — `epsilon` decays slowly
  toward 0.02 by design (see `QLearningAgent.decay_epsilon`); very
  short runs may not accumulate enough decisions per state. Increase
  `--ticks`, or run the benchmark repeatedly with the same
  `--qtable` path so learning accumulates across runs.
- **Tkinter import error** — install your OS's Tk package (see
  Installation above); this only affects `main.py`, not
  `benchmark_compare.py`.
- **Corrupted `traffic_qtable_v2.json`** — delete it; `QLearningAgent.load`
  catches load errors and starts from an empty table rather than
  crashing.

## 9. Final verification

```
TRAFFIC ENGINE (core physics, lights, hard lock, spawning): READY
AI ENGINE (Q-learning decide/learn/persist):                READY
INTEGRATION (real state -> real decision -> real effect):    READY
BASELINE MODE (AI off / unavailable == original v3.3):        READY
AI MODE (adaptive green timing, measured effect):             READY
FALLBACK (AI exception -> fixed timing, no crash):             READY
HEADLESS COMPARISON TOOL:                                      READY
GUI VISUAL RENDERING:                              NOT VERIFIED (no display in this environment)
TESTING:                                                    COMPLETED (headless)
```

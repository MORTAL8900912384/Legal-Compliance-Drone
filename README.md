# Legal Compliance Drone — Track 3 (Unit 4: First-Order Logic Agent)

**AI Express Hackathon** — an urban delivery drone that verifies airspace access
rules with a real First-Order Logic (FOL) inference engine before crossing into
any grid zone, visualised live with Pygame.

## What it demonstrates

- A **generic FOL inference engine** (`fol_engine.py`) — not a hardcoded
  if/else — with Robinson unification, **forward chaining** (fixpoint /
  data-driven) and **backward chaining** (SLD-resolution, goal-driven, with
  backtracking and negation-as-failure).
- The exact rule from the brief:
  `Restricted(x) ∧ NoPermit(drone) ⟹ ¬FlyOver(drone, x)`
  — implemented in `knowledge_base.py` as `R1-DenyFlyOver`, with `NoPermit`
  genuinely *derived* (not hardcoded) via negation-as-failure over `Permit` facts.
- A drone that **pauses at every restricted-zone boundary**, runs a live
  backward-chaining query, prints the full proof trace, and only moves once
  the query resolves — denying entry triggers a **BFS replan** around the
  zone (dynamic replanning); granting entry lets it proceed.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

A Pygame window opens showing the 8×8 grid on the left and the live FOL
reasoning trace + mission metrics on the right. The same trace is printed to
the terminal — put the two side by side for the required screen recording
split-screen.

Run `python test_engine.py` for a quick headless correctness check of the FOL
engine (unification, forward chaining, backward chaining) independent of the
graphics.

## Demo Video

[Watch the demo](https://drive.google.com/file/d/1fWf1lDj7d4uwKS-seKDWStTpLofIWbN9/view?usp=sharing)

## The scenario

```
Start (blue) ──▶ ZoneA (red, restricted, NO permit) ──▶ ZoneB (gold, restricted, permit held) ──▶ Goal (green)
```

`ZoneA` and `ZoneB` together form a solid wall across the middle of the grid
(cols 3–4, every row) — there is no way around it, only *through* one of the
two zones. This guarantees the demo always shows both outcomes:

1. Drone approaches **ZoneA** → queries `FlyOver(Drone1, ZoneA)` → **denied**
   (`Restricted(ZoneA) ∧ NoPermit(Drone1, ZoneA)`) → ZoneA is marked an
   obstacle → BFS **replans** a route.
2. The only detour runs straight into **ZoneB** → queries
   `FlyOver(Drone1, ZoneB)` → **allowed** (`Restricted(ZoneB) ∧
   Permit(Drone1, ZoneB)`) → drone proceeds to the goal.

Before takeoff, one forward-chaining pass pre-derives the full airspace
permission table (the drone's "pre-flight briefing"), printed to console.

## Predicates & rules

| Predicate | Meaning |
|---|---|
| `Drone(d)`, `Zone(x)` | domain facts (who/where exists) |
| `Restricted(x)` | zone `x` is restricted airspace |
| `Permit(d, x)` | drone `d` holds a flight permit for zone `x` |
| `NoPermit(d, x)` | derived: drone `d` has **no** permit for `x` |
| `FlyOver(d, x)` / `¬FlyOver(d, x)` | derived: `d` is/isn't cleared to cross `x` |

```
R0  Drone(d) ∧ Zone(x) ∧ ¬Permit(d, x)   ⟹  NoPermit(d, x)
R1  Restricted(x) ∧ NoPermit(d, x)       ⟹  ¬FlyOver(d, x)
R2  Drone(d) ∧ Zone(x) ∧ ¬Restricted(x)  ⟹  FlyOver(d, x)
R3  Restricted(x) ∧ Permit(d, x)         ⟹  FlyOver(d, x)
```

`Drone(d)`/`Zone(x)` exist because a negation-as-failure literal is only
decidable once its variables are ground (the standard Datalog "safety"
condition) — backward chaining grounds them from the query for free; forward
chaining needs an explicit finite domain to enumerate over.

## Project structure

```
fol_engine.py       generic unification + forward/backward chaining engine
knowledge_base.py   drone airspace predicates, rules, and KB builder
drone_sim.py        Pygame grid, BFS pathfinding/replanning, live trace panel
main.py             entry point
test_engine.py       headless correctness check for the FOL engine
generate_summary.py  builds SUMMARY.pdf from the content below
requirements.txt
```

## Tuning for the video

`MOVE_DELAY_MS`, `QUERY_DELAY_MS`, `RESULT_DELAY_MS` at the top of
`drone_sim.py` control animation pacing — slow them down if you want more
time to narrate over each pause.

## Submission checklist (per the hackathon sheet)

- [ ] Fill in team info in `generate_summary.py` and regenerate `SUMMARY.pdf`
      (`python generate_summary.py`), keep it in the repo root.
- [ ] Push this whole folder to a public/shared GitHub repo with commits from
      all 3 members.
- [ ] Record the 60–90s video (intro w/ team + repo link + track → live
      demo of a query/denial/replan/approval → final metrics) and link it in
      this README or upload the `.mp4`.
- [ ] Fill in `[GROUP ID]`, `[COURSE CODE]`, member names, and the GitHub URL
      placeholders in `SUMMARY.pdf`.

## Team

- Course Code: `[FILL IN]`
- Group ID: `[FILL IN]`
- Members: `[FILL IN]`, `[FILL IN]`, `[FILL IN]`
- GitHub Repository: `[FILL IN]`

"""Quick headless correctness check for fol_engine + knowledge_base.

Not a pytest suite (kept dependency-free for the 90-min hackathon repo) -
just run `python test_engine.py` and read PASS/FAIL.
"""

from knowledge_base import build_kb, can_fly_over, DRONE
from fol_engine import Literal, Const


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    return condition


def main():
    ok = True

    # Zone A: restricted, no permit -> must be DENIED
    # Zone B: restricted, WITH permit -> must be ALLOWED
    # Zone C: not restricted at all -> must be ALLOWED (open airspace)
    kb = build_kb(
        zones=["ZoneA", "ZoneB", "ZoneC"],
        restricted_zones=["ZoneA", "ZoneB"],
        permitted_zones=["ZoneB"],
    )

    proved, trace = can_fly_over(kb, "ZoneA")
    print("\n--- Backward-chain trace: FlyOver(Drone1, ZoneA) ---")
    print("\n".join(trace))
    ok &= check("ZoneA (restricted, no permit) denied", proved is False)

    proved, trace = can_fly_over(kb, "ZoneB")
    print("\n--- Backward-chain trace: FlyOver(Drone1, ZoneB) ---")
    print("\n".join(trace))
    ok &= check("ZoneB (restricted, has permit) allowed", proved is True)

    proved, trace = can_fly_over(kb, "ZoneC")
    print("\n--- Backward-chain trace: FlyOver(Drone1, ZoneC) ---")
    print("\n".join(trace))
    ok &= check("ZoneC (open airspace) allowed", proved is True)

    # Forward chaining: pre-derive the full permission table and check
    # it agrees with the backward-chain answers above.
    kb2 = build_kb(
        zones=["ZoneA", "ZoneB", "ZoneC"],
        restricted_zones=["ZoneA", "ZoneB"],
        permitted_zones=["ZoneB"],
    )
    fwd_log = []
    kb2.forward_chain(fwd_log)
    print("\n--- Forward-chain derivation log ---")
    print("\n".join(fwd_log))

    ok &= check(
        "Forward chain derives ~FlyOver(Drone1, ZoneA)",
        Literal("FlyOver", (DRONE, Const("ZoneA")), positive=False) in kb2.facts,
    )
    ok &= check(
        "Forward chain derives FlyOver(Drone1, ZoneB)",
        Literal("FlyOver", (DRONE, Const("ZoneB")), positive=True) in kb2.facts,
    )

    print("\n=== " + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED") + " ===")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

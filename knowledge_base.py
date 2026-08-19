"""
Drone airspace compliance scenario, built on top of the generic fol_engine.

Predicates
----------
Drone(d)             - d is a known drone                                 (domain fact)
Zone(x)               - x is a known airspace zone                        (domain fact)
Restricted(x)        - zone x is restricted airspace
Permit(d, x)         - drone d holds a flight permit for zone x           (base fact)
NoPermit(d, x)       - drone d does NOT hold a permit for zone x          (derived, NAF)
FlyOver(d, x)        - drone d is permitted to fly over zone x            (derived)
~FlyOver(d, x)       - drone d is explicitly forbidden from flying over x (derived)

Rules
-----
R0-NoPermit-by-NAF   :  Drone(d) AND Zone(x) AND ~Permit(d, x)   =>  NoPermit(d, x)
R1-DenyFlyOver       :  Restricted(x) AND NoPermit(d, x)         =>  ~FlyOver(d, x)
R2-AllowOpenAirspace :  Drone(d) AND Zone(x) AND ~Restricted(x)  =>  FlyOver(d, x)
R3-AllowWithPermit   :  Restricted(x) AND Permit(d, x)           =>  FlyOver(d, x)

R1 is exactly the rule given in the assignment brief:
    Restricted(x) AND NoPermit(drone) => ~FlyOver(drone, x)
(here NoPermit is genuinely *derived* via negation-as-failure over Permit
facts, rather than hardcoded, and carries the zone argument so a drone can
hold a permit for one zone but not another.)

Why Drone(d)/Zone(x) domain facts exist: a negation-as-failure literal like
~Permit(d, x) is only decidable once d and x are *ground* - the classic
Datalog "safety" requirement. Backward chaining grounds them for free from
the query; forward chaining has no query to ground from, so it needs an
explicit finite domain (Drone/Zone facts) to enumerate over. Without them,
R0/R2 would never fire during forward chaining.
"""

from fol_engine import Var, Const, Literal, Rule, KnowledgeBase

DRONE = Const("Drone1")


def L(pred, *args, positive=True):
    return Literal(pred, tuple(args), positive)


def build_kb(zones, restricted_zones, permitted_zones):
    """
    zones             : iterable[str] - every named zone in the world (the FOL domain)
    restricted_zones  : iterable[str] - subset of `zones` that is restricted airspace
    permitted_zones   : iterable[str] - subset of `zones` DRONE holds a permit for

    Returns a ready-to-query fol_engine.KnowledgeBase.
    """
    facts = {L("Drone", DRONE)}
    for zone in zones:
        facts.add(L("Zone", Const(zone)))
    for zone in restricted_zones:
        facts.add(L("Restricted", Const(zone)))
    for zone in permitted_zones:
        facts.add(L("Permit", DRONE, Const(zone)))

    d, x = Var("d"), Var("x")
    rules = [
        Rule(
            "R0-NoPermit-by-NAF",
            body=(L("Drone", d), L("Zone", x), L("Permit", d, x, positive=False)),
            head=L("NoPermit", d, x),
        ),
        Rule(
            "R1-DenyFlyOver",
            body=(L("Restricted", x), L("NoPermit", d, x)),
            head=L("FlyOver", d, x, positive=False),
        ),
        Rule(
            "R2-AllowOpenAirspace",
            body=(L("Drone", d), L("Zone", x), L("Restricted", x, positive=False)),
            head=L("FlyOver", d, x),
        ),
        Rule(
            "R3-AllowWithPermit",
            body=(L("Restricted", x), L("Permit", d, x)),
            head=L("FlyOver", d, x),
        ),
    ]
    return KnowledgeBase(facts, rules)


def can_fly_over(kb, zone_name):
    """Backward-chain query: may DRONE fly over `zone_name`? -> (bool, trace)."""
    goal = L("FlyOver", DRONE, Const(zone_name))
    return kb.query(goal)

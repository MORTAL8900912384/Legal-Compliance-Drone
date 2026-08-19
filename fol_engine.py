"""
Generic First-Order Logic inference engine.

Implements:
  - Term representation (Var / Const) + Robinson unification
  - Signed literals (positive/negative), e.g. Restricted(ZoneA) or ~FlyOver(Drone1, ZoneA)
  - Horn-clause-style Rules with negation-as-failure (NAF) support in rule bodies
  - Forward chaining (fixpoint / data-driven)
  - Backward chaining (SLD-resolution style, goal-driven, with backtracking + NAF)

This module is domain-agnostic - the drone airspace scenario lives in
knowledge_base.py and only supplies facts/rules built from these primitives.
"""

from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------
# Terms
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Var:
    name: str

    def __repr__(self):
        return f"?{self.name}"


@dataclass(frozen=True)
class Const:
    name: str

    def __repr__(self):
        return self.name


def is_var(t):
    return isinstance(t, Var)


def is_ground(literal):
    return all(not is_var(a) for a in literal.args)


# --------------------------------------------------------------------------
# Literals & Rules
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Literal:
    """A signed predicate application, e.g. Restricted(ZoneA) or ~FlyOver(Drone1, ZoneA).

    positive=False means the *negation* of the atom - used both as an
    explicit derived fact (e.g. the head of a "deny" rule) and, in a rule
    body, as a negation-as-failure ("NAF") condition: "cannot prove Permit(...)".
    """
    predicate: str
    args: tuple
    positive: bool = True

    def __repr__(self):
        sign = "" if self.positive else "~"
        args = ", ".join(map(str, self.args))
        return f"{sign}{self.predicate}({args})"


@dataclass(frozen=True)
class Rule:
    name: str
    body: tuple  # tuple[Literal, ...]
    head: Literal

    def __repr__(self):
        body = " AND ".join(map(str, self.body)) if self.body else "TRUE"
        return f"{self.name}: {body}  =>  {self.head}"


# --------------------------------------------------------------------------
# Unification
# --------------------------------------------------------------------------

def unify(a, b, theta):
    if theta is None:
        return None
    if a == b:
        return theta
    if is_var(a):
        return _unify_var(a, b, theta)
    if is_var(b):
        return _unify_var(b, a, theta)
    return None  # two distinct constants never unify


def _unify_var(v, x, theta):
    if v in theta:
        return unify(theta[v], x, theta)
    if is_var(x) and x in theta:
        return unify(v, theta[x], theta)
    theta2 = dict(theta)
    theta2[v] = x
    return theta2


def unify_literals(l1, l2, theta):
    if theta is None:
        return None
    if l1.predicate != l2.predicate or l1.positive != l2.positive or len(l1.args) != len(l2.args):
        return None
    for a, b in zip(l1.args, l2.args):
        theta = unify(a, b, theta)
        if theta is None:
            return None
    return theta


def substitute(literal, theta):
    args = tuple(theta.get(a, a) if is_var(a) else a for a in literal.args)
    return Literal(literal.predicate, args, literal.positive)


def pretty_theta(theta):
    if not theta:
        return "{}"
    return "{" + ", ".join(f"{k}={v}" for k, v in theta.items()) + "}"


# --------------------------------------------------------------------------
# Knowledge Base
# --------------------------------------------------------------------------

class KnowledgeBase:
    def __init__(self, facts=None, rules=None):
        self.facts: set[Literal] = set(facts or [])
        self.rules: list[Rule] = list(rules or [])

    def add_fact(self, literal: Literal):
        self.facts.add(literal)

    # ---------------------------------------------------------------- #
    # Forward chaining - data-driven, runs every rule to fixpoint.     #
    # ---------------------------------------------------------------- #
    def forward_chain(self, log: Optional[list] = None):
        """Apply all rules repeatedly until no new fact is derived.

        Returns a list of (rule, theta, new_fact) triples in derivation order.
        """
        derived = []
        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                for theta in self._match_body(rule.body, {}):
                    head = substitute(rule.head, theta)
                    if is_ground(head) and head not in self.facts:
                        self.facts.add(head)
                        derived.append((rule, theta, head))
                        if log is not None:
                            log.append(
                                f"[FORWARD] {rule.name}  {pretty_theta(theta)}  =>  {head}"
                            )
                        changed = True
        return derived

    def _match_body(self, body, theta):
        """Yield every substitution (extending theta) that satisfies `body`."""
        if not body:
            yield theta
            return
        first, rest = body[0], body[1:]
        if first.positive:
            for fact in list(self.facts):
                theta2 = unify_literals(first, fact, dict(theta))
                if theta2 is not None:
                    yield from self._match_body(rest, theta2)
        else:
            grounded = substitute(first, theta)
            if is_ground(grounded):
                positive_form = Literal(grounded.predicate, grounded.args, True)
                if not any(True for _ in self.backward_chain(positive_form)):
                    yield from self._match_body(rest, theta)

    # ---------------------------------------------------------------- #
    # Backward chaining - goal-driven SLD resolution with NAF.         #
    # ---------------------------------------------------------------- #
    def backward_chain(self, goal: Literal, theta=None, depth=0, log=None):
        """Generator yielding (theta, log) for every way `goal` can be proved.

        `log` is a shared, growing list of human-readable trace lines so the
        caller can print/display the full reasoning path (including dead ends).
        """
        theta = theta if theta is not None else {}
        log = log if log is not None else []
        indent = "  " * depth
        goal_g = substitute(goal, theta)

        if not goal_g.positive:
            # Negation as failure: goal_g must be ground at this point.
            positive_goal = Literal(goal_g.predicate, goal_g.args, True)
            proved = any(True for _ in self.backward_chain(positive_goal, {}, depth + 1, []))
            if not proved:
                log.append(f"{indent}OK {goal_g}   [NAF: {positive_goal} is not provable]")
                yield theta, log
            else:
                log.append(f"{indent}NO {goal_g}   [NAF failed: {positive_goal} IS provable]")
            return

        found = False
        for fact in self.facts:
            theta2 = unify_literals(goal_g, fact, {})
            if theta2 is not None:
                found = True
                log.append(f"{indent}OK {goal_g}   [known fact]")
                merged = dict(theta)
                merged.update(theta2)
                yield merged, log

        for rule in self.rules:
            theta_h = unify_literals(goal_g, rule.head, {})
            if theta_h is None:
                continue
            log.append(f"{indent}?  {goal_g}   <= trying rule '{rule.name}'")
            for theta_final, log2 in self._prove_body(rule.body, theta_h, depth + 1, log, rule.name, goal_g):
                found = True
                merged = dict(theta)
                merged.update(theta_final)
                yield merged, log2

        if not found:
            log.append(f"{indent}NO {goal_g}   [no matching facts or rules]")

    def _prove_body(self, body, theta, depth, log, rule_name, original_goal):
        if not body:
            log.append(f"{'  ' * depth}OK {substitute(original_goal, theta)}   [via {rule_name}]")
            yield theta, log
            return
        first, rest = body[0], body[1:]
        for theta2, log2 in self.backward_chain(first, theta, depth, log):
            yield from self._prove_body(rest, theta2, depth, log2, rule_name, original_goal)

    def query(self, goal: Literal):
        """Convenience wrapper: returns (proved: bool, trace: list[str])."""
        log = []
        for _theta, log in self.backward_chain(goal, {}, 0, log):
            return True, log
        return False, log

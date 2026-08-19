"""
Pygame visualisation: an urban delivery drone crossing a grid of airspace
zones. Before entering any restricted zone the drone PAUSES, fires a
backward-chaining FOL query against the knowledge base built in
knowledge_base.py, prints/renders the full proof trace, and only then
either (a) proceeds, or (b) treats the zone as a no-go obstacle and
replans (BFS) a new route around it - live "dynamic replanning".

A one-off forward-chaining pass runs before takeoff to pre-derive the full
airspace permission table (the drone's "pre-flight briefing").
"""

import sys
import time
from collections import deque

import pygame

# Windows terminals often default to a legacy codepage (cp1252) that can't
# encode every character - never let a stray glyph crash the live demo.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

from fol_engine import Const
from knowledge_base import DRONE, build_kb, can_fly_over

# --------------------------------------------------------------------------
# Grid / scenario configuration
# --------------------------------------------------------------------------

GRID_COLS, GRID_ROWS = 8, 8
CELL = 64

START = (0, 1)
GOAL = (7, 1)

# Rectangular zones as (col_range, row_range), inclusive. ZoneA and ZoneB
# together span cols 3-4 across *every* row - a solid wall between the
# start and goal halves of the grid with no open gap. The only way through
# is via ZoneA (top) or ZoneB (bottom), which is what forces the drone to
# actually encounter both a denial (ZoneA) and an approval (ZoneB) instead
# of just detouring around everything.
ZONE_DEFS = {
    "ZoneA": {"cols": range(3, 5), "rows": range(0, 4)},  # restricted, NO permit
    "ZoneB": {"cols": range(3, 5), "rows": range(4, 8)},  # restricted, WITH permit
}
RESTRICTED_ZONES = ["ZoneA", "ZoneB"]
PERMITTED_ZONES = ["ZoneB"]

MOVE_DELAY_MS = 450
QUERY_DELAY_MS = 1600
RESULT_DELAY_MS = 2000

# --------------------------------------------------------------------------
# Colours
# --------------------------------------------------------------------------

BG = (24, 26, 34)
GRID_LINE = (58, 62, 78)
OPEN_CELL = (233, 236, 244)
ZONE_COLORS = {"ZoneA": (231, 111, 81), "ZoneB": (233, 196, 106)}
ZONE_BLOCKED_COLOR = (140, 40, 40)
START_COLOR = (52, 152, 219)
GOAL_COLOR = (46, 204, 113)
DRONE_COLOR = (25, 29, 38)
TEXT = (232, 234, 240)
DIM_TEXT = (150, 155, 170)
LOG_BG = (16, 17, 23)
BANNER_QUERY = (233, 196, 106)
BANNER_ALLOW = (46, 204, 113)
BANNER_DENY = (231, 76, 60)

GRID_ORIGIN = (24, 96)
PANEL_X = GRID_ORIGIN[0] + GRID_COLS * CELL + 36
PANEL_W = 420
WIN_W = PANEL_X + PANEL_W + 24
WIN_H = GRID_ORIGIN[1] + GRID_ROWS * CELL + 56


# --------------------------------------------------------------------------
# Grid helpers
# --------------------------------------------------------------------------

def zone_of(cell):
    col, row = cell
    for name, span in ZONE_DEFS.items():
        if col in span["cols"] and row in span["rows"]:
            return name
    return None


def zone_cells(name):
    span = ZONE_DEFS[name]
    return {(c, r) for c in span["cols"] for r in span["rows"]}


def in_bounds(cell):
    c, r = cell
    return 0 <= c < GRID_COLS and 0 <= r < GRID_ROWS


def bfs(start, goal, blocked):
    """4-directional BFS. Returns (path_list_or_None, nodes_expanded)."""
    if start == goal:
        return [start], 0
    frontier = deque([start])
    came_from = {start: None}
    expanded = 0
    while frontier:
        cur = frontier.popleft()
        expanded += 1
        if cur == goal:
            path = []
            node = cur
            while node is not None:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path, expanded
        c, r = cur
        for nxt in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
            if in_bounds(nxt) and nxt not in blocked and nxt not in came_from:
                came_from[nxt] = cur
                frontier.append(nxt)
    return None, expanded


# --------------------------------------------------------------------------
# Simulation driver (generator of render-ready state snapshots)
# --------------------------------------------------------------------------

class Metrics:
    def __init__(self):
        self.steps_moved = 0
        self.queries_run = 0
        self.replans = 0
        self.nodes_expanded = 0
        self.start_time = time.time()

    def elapsed(self):
        return time.time() - self.start_time


class DroneMission:
    """Drives the drone step by step; each call to `advance()` performs
    exactly one unit of work (a move, or a query-and-decide) and returns
    a dict describing what happened, for the renderer to display."""

    def __init__(self, kb):
        self.kb = kb
        self.metrics = Metrics()
        self.blocked = set()
        self.position = START
        self.current_zone = zone_of(START)
        self.done = False
        self.console_log = []
        path, expanded = bfs(self.position, GOAL, self.blocked)
        self.metrics.nodes_expanded += expanded
        self.path = path
        self.path_idx = 1

    def _print(self, line=""):
        print(line)
        self.console_log.append(line)

    def advance(self):
        if self.done:
            return {"event": "done"}

        if self.path is None:
            self.done = True
            self._print("!! NO ROUTE AVAILABLE - mission aborted.")
            return {"event": "stuck"}

        if self.path_idx >= len(self.path):
            self.done = True
            self._print(f"\n=== DELIVERY COMPLETE at {self.position} ===")
            return {"event": "arrived"}

        next_cell = self.path[self.path_idx]
        next_zone = zone_of(next_cell)

        if next_zone is not None and next_zone != self.current_zone:
            # Boundary of a NAMED zone: pause and consult the FOL engine.
            self.metrics.queries_run += 1
            self._print(f"\n--- Approaching boundary of {next_zone} at {next_cell} ---")
            self._print(f"Querying FOL engine:  FlyOver({DRONE.name}, {next_zone}) ?")
            proved, trace = can_fly_over(self.kb, next_zone)
            for line in trace:
                self._print("    " + line)

            if proved:
                self._print(f"RESULT: ALLOWED - entering {next_zone}.")
                self.position = next_cell
                self.current_zone = next_zone
                self.path_idx += 1
                self.metrics.steps_moved += 1
                return {
                    "event": "query_allowed",
                    "zone": next_zone,
                    "trace": trace,
                    "position": self.position,
                }
            else:
                self._print(f"RESULT: DENIED - {next_zone} is a no-fly zone for this drone.")
                self.blocked |= zone_cells(next_zone)
                self.metrics.replans += 1
                self._print(f"Replanning route around {next_zone} (BFS from {self.position})...")
                new_path, expanded = bfs(self.position, GOAL, self.blocked)
                self.metrics.nodes_expanded += expanded
                self.path = new_path
                self.path_idx = 1
                if new_path is None:
                    self._print("!! No detour exists - grounding drone.")
                return {
                    "event": "query_denied",
                    "zone": next_zone,
                    "trace": trace,
                    "position": self.position,
                }

        # Ordinary move: same zone (or open airspace) — no boundary crossing.
        self.position = next_cell
        self.current_zone = next_zone
        self.path_idx += 1
        self.metrics.steps_moved += 1
        return {"event": "move", "position": self.position}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def cell_rect(cell):
    col, row = cell
    x = GRID_ORIGIN[0] + col * CELL
    y = GRID_ORIGIN[1] + row * CELL
    return pygame.Rect(x, y, CELL, CELL)


def draw_grid(screen, mission):
    for col in range(GRID_COLS):
        for row in range(GRID_ROWS):
            cell = (col, row)
            zone = zone_of(cell)
            if zone is None:
                color = OPEN_CELL
            elif cell in mission.blocked:
                color = ZONE_BLOCKED_COLOR
            else:
                color = ZONE_COLORS[zone]
            pygame.draw.rect(screen, color, cell_rect(cell))
            pygame.draw.rect(screen, GRID_LINE, cell_rect(cell), 1)

    pygame.draw.rect(screen, START_COLOR, cell_rect(START), 4)
    pygame.draw.rect(screen, GOAL_COLOR, cell_rect(GOAL), 4)


def draw_drone(screen, mission):
    rect = cell_rect(mission.position)
    cx, cy = rect.center
    r = CELL // 3
    pygame.draw.circle(screen, DRONE_COLOR, (cx, cy), r)
    pygame.draw.circle(screen, (255, 255, 255), (cx, cy), r, 2)


def draw_legend(screen, font):
    x, y = GRID_ORIGIN[0], GRID_ORIGIN[1] + GRID_ROWS * CELL + 12
    items = [
        (START_COLOR, "Start"),
        (GOAL_COLOR, "Goal / delivery point"),
        (ZONE_COLORS["ZoneA"], "Restricted, NO permit"),
        (ZONE_COLORS["ZoneB"], "Restricted, permit held"),
        (ZONE_BLOCKED_COLOR, "Denied -> treated as obstacle"),
    ]
    for i, (color, label) in enumerate(items):
        lx = x + (i % 3) * 195
        ly = y + (i // 3) * 22
        pygame.draw.rect(screen, color, pygame.Rect(lx, ly + 3, 14, 14))
        screen.blit(font.render(label, True, DIM_TEXT), (lx + 20, ly))


def wrap_text(text, font, max_width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.size(trial)[0] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_panel(screen, mission, fonts, banner):
    font_h, font_body, font_mono, font_small = fonts
    x = PANEL_X
    y = 96

    screen.blit(font_h.render("FOL INFERENCE ENGINE", True, TEXT), (x, 60))

    # Banner
    banner_text, banner_color = banner
    banner_rect = pygame.Rect(x, y, PANEL_W, 54)
    pygame.draw.rect(screen, banner_color, banner_rect, border_radius=6)
    lines = wrap_text(banner_text, font_body, PANEL_W - 20)
    for i, line in enumerate(lines[:2]):
        surf = font_body.render(line, True, (15, 15, 20))
        screen.blit(surf, (x + 10, y + 8 + i * 20))
    y += 54 + 14

    # Trace log
    screen.blit(font_small.render("REASONING TRACE (live console mirrors this):", True, DIM_TEXT), (x, y))
    y += 20
    log_rect = pygame.Rect(x, y, PANEL_W, 300)
    pygame.draw.rect(screen, LOG_BG, log_rect, border_radius=4)

    all_lines = []
    for line in mission.console_log[-14:]:
        all_lines.extend(wrap_text(line, font_mono, PANEL_W - 20))
    visible = all_lines[-16:]
    for i, line in enumerate(visible):
        color = TEXT
        if line.strip().startswith("OK") or "ALLOWED" in line:
            color = BANNER_ALLOW
        elif line.strip().startswith("NO") or "DENIED" in line or "!!" in line:
            color = BANNER_DENY
        elif line.strip().startswith("?"):
            color = BANNER_QUERY
        screen.blit(font_mono.render(line, True, color), (x + 10, y + 8 + i * 18))
    y += 300 + 16

    # Metrics
    m = mission.metrics
    screen.blit(font_small.render("MISSION METRICS", True, DIM_TEXT), (x, y))
    y += 20
    metric_lines = [
        f"Steps moved (path cost): {m.steps_moved}",
        f"FOL queries executed:    {m.queries_run}",
        f"Dynamic replans:         {m.replans}",
        f"BFS nodes expanded:      {m.nodes_expanded}",
        f"Elapsed time:            {m.elapsed():5.1f}s",
    ]
    for i, line in enumerate(metric_lines):
        screen.blit(font_mono.render(line, True, TEXT), (x + 10, y + i * 20))


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------

def pump_and_wait(ms):
    """Keep the window responsive during a scripted pause."""
    clock_end = pygame.time.get_ticks() + ms
    while pygame.time.get_ticks() < clock_end:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
        pygame.time.delay(16)


def run_simulation():
    pygame.init()
    pygame.display.set_caption("Legal Compliance Drone — FOL Airspace Inference")
    screen = pygame.display.set_mode((WIN_W, WIN_H))

    font_title = pygame.font.SysFont("consolas", 22, bold=True)
    font_h = pygame.font.SysFont("consolas", 16, bold=True)
    font_body = pygame.font.SysFont("consolas", 15, bold=True)
    font_mono = pygame.font.SysFont("consolas", 13)
    font_small = pygame.font.SysFont("consolas", 12, bold=True)
    fonts = (font_h, font_body, font_mono, font_small)

    kb = build_kb(
        zones=list(ZONE_DEFS.keys()),
        restricted_zones=RESTRICTED_ZONES,
        permitted_zones=PERMITTED_ZONES,
    )

    print("=" * 70)
    print("PRE-FLIGHT BRIEFING - forward-chaining the full airspace rule set")
    print("=" * 70)
    fwd_log = []
    kb.forward_chain(fwd_log)
    for line in fwd_log:
        print(line)
    print("=" * 70)
    print("TAKEOFF - live backward-chaining begins")
    print("=" * 70)

    mission = DroneMission(kb)
    banner = ("Mission start — cleared for open airspace.", (90, 95, 110))

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill(BG)
        title = font_title.render("LEGAL COMPLIANCE DRONE — FOL Airspace Inference Demo", True, TEXT)
        screen.blit(title, (24, 24))
        subtitle = font_small.render(
            "Track 3 · Unit 4 First-Order Logic Agent — forward + backward chaining", True, DIM_TEXT
        )
        screen.blit(subtitle, (24, 52))

        draw_grid(screen, mission)
        draw_drone(screen, mission)
        draw_legend(screen, font_small)
        draw_panel(screen, mission, fonts, banner)
        pygame.display.flip()

        if mission.done:
            pump_and_wait(300)
            continue

        result = mission.advance()
        event_type = result["event"]

        if event_type == "move":
            banner = (f"Cruising through open airspace toward {GOAL}.", (90, 95, 110))
            screen.fill(BG)
            screen.blit(title, (24, 24))
            screen.blit(subtitle, (24, 52))
            draw_grid(screen, mission)
            draw_drone(screen, mission)
            draw_legend(screen, font_small)
            draw_panel(screen, mission, fonts, banner)
            pygame.display.flip()
            pump_and_wait(MOVE_DELAY_MS)

        elif event_type in ("query_allowed", "query_denied"):
            zone = result["zone"]
            banner = (f"PAUSED at zone boundary — querying FlyOver(Drone1, {zone})...", BANNER_QUERY)
            screen.fill(BG)
            screen.blit(title, (24, 24))
            screen.blit(subtitle, (24, 52))
            draw_grid(screen, mission)
            draw_drone(screen, mission)
            draw_legend(screen, font_small)
            draw_panel(screen, mission, fonts, banner)
            pygame.display.flip()
            pump_and_wait(QUERY_DELAY_MS)

            if event_type == "query_allowed":
                banner = (f"ALLOWED — permit verified for {zone}. Proceeding.", BANNER_ALLOW)
            else:
                banner = (f"DENIED — {zone} is restricted, no permit. Replanning route.", BANNER_DENY)
            screen.fill(BG)
            screen.blit(title, (24, 24))
            screen.blit(subtitle, (24, 52))
            draw_grid(screen, mission)
            draw_drone(screen, mission)
            draw_legend(screen, font_small)
            draw_panel(screen, mission, fonts, banner)
            pygame.display.flip()
            pump_and_wait(RESULT_DELAY_MS)

        elif event_type == "arrived":
            banner = ("Delivery complete — mission success.", BANNER_ALLOW)

        elif event_type == "stuck":
            banner = ("No legal route found — mission aborted.", BANNER_DENY)

    pygame.quit()


if __name__ == "__main__":
    run_simulation()

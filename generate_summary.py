"""
Generates SUMMARY.pdf — the 1-page Technical Summary Sheet required by the
hackathon submission sheet (Header/Team, PEAS matrix, Algorithmic
Formulation, Complexity Analysis).

Fill in the TEAM_INFO block below with your real details, then run:
    python generate_summary.py
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --------------------------------------------------------------------------
# EDIT THIS BLOCK with your team's real details before submitting.
# --------------------------------------------------------------------------
TEAM_INFO = {
    "course_code": "[COURSE CODE]",
    "group_id": "[GROUP ID]",
    "members": "[Member 1 Name], [Member 2 Name], [Member 3 Name]",
    "track": "Track 3 — Legal Compliance Drone (Unit 4: First-Order Logic Agent)",
    "github_url": "[GITHUB REPOSITORY URL]",
}
# --------------------------------------------------------------------------

styles = getSampleStyleSheet()
h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=14, spaceAfter=4, spaceBefore=0)
h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=10.5, spaceAfter=3, spaceBefore=8,
                     textColor=colors.HexColor("#1a3c6e"))
body = ParagraphStyle("body", parent=styles["Normal"], fontSize=8.7, leading=11.5)
small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.3, leading=10.8,
                        textColor=colors.HexColor("#333333"))
cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7.6, leading=9.6)
cell_bold = ParagraphStyle("cell_bold", parent=cell, fontName="Helvetica-Bold")


def P(text, style=cell):
    return Paragraph(text, style)


def build_pdf(path="SUMMARY.pdf"):
    doc = SimpleDocTemplate(
        path,
        pagesize=LETTER,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
    )
    story = []

    # --- Header & Team Info -------------------------------------------------
    story.append(Paragraph("AI Express Hackathon — Technical Summary Sheet", h1))
    header_table = Table(
        [
            ["Course Code:", TEAM_INFO["course_code"], "Group ID:", TEAM_INFO["group_id"]],
            ["Members:", TEAM_INFO["members"], "", ""],
            ["Selected Track:", TEAM_INFO["track"], "", ""],
            ["GitHub Repository:", TEAM_INFO["github_url"], "", ""],
        ],
        colWidths=[1.1 * inch, 3.3 * inch, 0.9 * inch, 1.7 * inch],
    )
    header_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.7),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("SPAN", (1, 1), (3, 1)),
        ("SPAN", (1, 2), (3, 2)),
        ("SPAN", (1, 3), (3, 3)),
    ]))
    story.append(header_table)

    # --- PEAS Framework Matrix ----------------------------------------------
    story.append(Paragraph("PEAS Framework Matrix", h2))
    peas_data = [
        [P("Performance Measure", cell_bold), P("Environment", cell_bold),
         P("Actuators", cell_bold), P("Sensors", cell_bold)],
        [
            P("Reach the delivery goal cell while never crossing FlyOver-denied "
              "airspace; minimise total moves (path cost) and number of replans."),
            P("8x8 discrete grid; partially observable (a zone's Restricted/"
              "Permit status is confirmed only via an FOL query at its boundary); "
              "static rule set, deterministic, single-agent."),
            P("One-cell move (up/down/left/right); hold/pause at a zone "
              "boundary while a query resolves."),
            P("Position sensor (current cell); zone-boundary detector "
              "(triggers an FOL query); knowledge-base reader (Restricted / "
              "Permit facts)."),
        ],
    ]
    peas_table = Table(peas_data, colWidths=[1.55 * inch, 1.85 * inch, 1.35 * inch, 1.35 * inch])
    peas_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe6f3")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(peas_table)

    # --- Core Algorithmic Formulation ---------------------------------------
    story.append(Paragraph("Core Algorithmic Formulation", h2))
    story.append(Paragraph(
        "<b>State space:</b> S = (cell, blocked_zone_set) where cell is the drone's grid "
        "position and blocked_zone_set is the set of zones so far denied by the FOL engine. "
        "<b>Initial state:</b> (Start cell, &#8709;). <b>Goal test:</b> cell == Goal cell. "
        "<b>Path cost:</b> uniform, 1 per grid move (4-directional). "
        "<b>Path planning:</b> Breadth-First Search (optimal under uniform cost), re-invoked "
        "from the drone's current cell whenever a zone query is denied (dynamic replanning), "
        "with the denied zone's cells added to blocked_zone_set as obstacles.",
        body,
    ))
    story.append(Paragraph(
        "<b>FOL rules (Horn-clause form, executed by a generic unification-based engine "
        "supporting both forward and backward chaining with negation-as-failure):</b>",
        body,
    ))
    rules_text = (
        "R0&nbsp;&nbsp; Drone(d) &and; Zone(x) &and; &not;Permit(d,x)&nbsp; &rArr;&nbsp; NoPermit(d,x)<br/>"
        "R1&nbsp;&nbsp; Restricted(x) &and; NoPermit(d,x)&nbsp; &rArr;&nbsp; &not;FlyOver(d,x)  "
        "&nbsp;<i>(the rule given in the brief)</i><br/>"
        "R2&nbsp;&nbsp; Drone(d) &and; Zone(x) &and; &not;Restricted(x)&nbsp; &rArr;&nbsp; FlyOver(d,x)<br/>"
        "R3&nbsp;&nbsp; Restricted(x) &and; Permit(d,x)&nbsp; &rArr;&nbsp; FlyOver(d,x)"
    )
    story.append(Paragraph(rules_text, small))
    story.append(Paragraph(
        "Backward chaining (SLD resolution) answers each live boundary query "
        "FlyOver(Drone1, Zone) goal-directed, with a full proof trace. Forward chaining runs "
        "once pre-flight to derive the complete permission table over all known zones.",
        body,
    ))

    # --- Complexity Analysis -------------------------------------------------
    story.append(Paragraph("Complexity Analysis", h2))
    complexity_data = [
        [P("Component", cell_bold), P("Theoretical", cell_bold), P("Observed (this run)", cell_bold)],
        [P("FOL backward-chain query"),
         P("O(b^d), b=rules/facts matching a goal, d=max rule-chain depth "
           "(d=2 here) &mdash; effectively O(1) for this finite, acyclic, "
           "function-free rule set"),
         P("2 queries, each resolved in &lt;5 proof steps, &lt;1 ms")],
        [P("FOL forward chaining"),
         P("O(|rules| . |facts|^k), k=max body literals (k=3) per fixpoint "
           "pass, bounded by finite derivable fact set |F|"),
         P("3 new facts derived in 1 pass over 4 rules")],
        [P("BFS path (re)plan"),
         P("O(V+E) per plan on an RxC grid = O(R.C); total = O(replans . R.C)"),
         P("1 initial plan + 1 replan, 89 total nodes expanded on an 8x8 grid (V=64)")],
        [P("End-to-end mission"),
         P("O(R.C) dominates (grid search over shallow, constant-depth logic queries)"),
         P("13 moves (path cost), ~13-20s wall-clock depending on animation pacing")],
    ]
    complexity_table = Table(complexity_data, colWidths=[1.3 * inch, 3.15 * inch, 2.05 * inch])
    complexity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe6f3")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(complexity_table)

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>Re-run `python main.py` and read the Mission Metrics panel to reproduce/verify "
        "the observed figures above.</i>",
        small,
    ))

    doc.build(story)
    print(f"Wrote {path}")


if __name__ == "__main__":
    build_pdf()

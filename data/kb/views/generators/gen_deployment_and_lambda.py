#!/usr/bin/env python3
"""Figure 6 (deployment view) and Figure 7 (lambda / prod-preprod view)."""
import importlib.util

spec = importlib.util.spec_from_file_location("db", "/home/claude/archi/diagram_base.py")
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)
box, zone, arrow, label, svg = db.box, db.zone, db.arrow, db.label, db.svg
COL, TXT, TXT2, ARROW = db.COL, db.TXT, db.TXT2, db.ARROW


def plain(pts, width=1.8, dashed=False):
    d = "M" + " L".join(f"{p[0]} {p[1]}" for p in pts)
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    return f'<path d="{d}" fill="none" stroke="{ARROW}" stroke-width="{width}"{dash}/>'


# ==================================================== FIGURE 6 — DEPLOYMENT
b = []
b.append(zone(60, 50, 1280, 490, "A · Deployment of telemetry collection", "coral"))
b.append(box(100, 100, 560, 64, "purple", "Git  →  Rancher Fleet",
             ["Agent and gateway configuration deployed as bundles"], tsize=19))
b.append(box(100, 200, 240, 80, "purple", "Management cluster",
             ["EDOT agent (DaemonSet)"], tsize=18))
b.append(box(420, 200, 240, 80, "purple", "MCX workload clusters",
             ["EDOT agent (DaemonSet)"], tsize=18))
b.append(box(740, 200, 240, 80, "gray", "Ericsson ENM",
             ["FM / PM feeds — no agent"], tsize=18))
b.append(box(1060, 200, 240, 80, "teal", "Transport devices",
             ["syslog, SNMP — no agent"], tsize=18))
b.append(arrow([(220, 164), (220, 198)]))
b.append(arrow([(540, 164), (540, 198)]))
b.append(plain([(220, 280), (220, 310), (1180, 310), (1180, 280)]))
b.append(plain([(540, 280), (540, 310)]))
b.append(plain([(860, 280), (860, 310)]))
b.append(arrow([(700, 310), (700, 348)]))
b.append(box(470, 350, 460, 80, "coral", "OTel gateway collectors",
             ["OTLP receivers · syslog · SNMP · NBI polling", "filtering, pseudonymization, tee"], tsize=19))
b.append(arrow([(600, 430), (600, 468)]))
b.append(box(300, 470, 480, 60, "coral", "Elasticsearch production", [], tsize=19))
b.append(arrow([(870, 430), (1080, 430), (1080, 468)], dashed=True))
b.append(box(880, 470, 400, 60, "teal", "Elasticsearch pre-production", [], tsize=19))
b.append(label(1000, 452, "tap", 14))

b.append(zone(60, 570, 1280, 400, "B · Closed-loop playbook triggered on alarm, executed on approval", "amber"))
b.append(box(100, 630, 260, 80, "coral", "Alerting rule",
             ["Kibana / Elasticsearch"], tsize=18))
b.append(box(420, 630, 260, 80, "coral", "EDA rulebook",
             ["dedup, kill switch, lock"], tsize=18))
b.append(box(740, 630, 260, 80, "amber", "AWX workflow",
             ["launched with alarm context"], tsize=18))
b.append(box(1060, 630, 260, 80, "amber", "Approval node",
             ["operator button, timeout"], tsize=18))
b.append(arrow([(360, 670), (418, 670)]))
b.append(arrow([(680, 670), (738, 670)]))
b.append(arrow([(1000, 670), (1058, 670)]))
b.append(box(740, 740, 260, 58, "amber", "Operator-initiated action",
             ["same workflow and approval"], tsize=17, ssize=14))
b.append(arrow([(870, 740), (870, 712)]))
b.append(arrow([(1190, 710), (1190, 818)]))
b.append(box(1000, 820, 300, 80, "purple", "Playbook execution",
             ["pre-checks, apply, post-checks"], tsize=18))
b.append(arrow([(998, 860), (942, 860)]))
b.append(box(600, 820, 340, 80, "purple", "Target domain",
             ["NETCONF · Fleet commit · ENM NBI"], tsize=18))
b.append(arrow([(598, 860), (542, 860)]))
b.append(box(100, 820, 440, 80, "gray", "ServiceNow",
             ["incident opened, then updated with outcome"], tsize=18))
b.append(arrow([(560, 710), (560, 790), (430, 790), (430, 818)]))
svg(1400, 1010, "\n".join(b), "/home/claude/archi/v2_deployment_view.svg")

# ==================================================== FIGURE 7 — LAMBDA
b = []
b.append(zone(60, 60, 610, 520, "Production zone — armed", "purple"))
b.append(box(120, 115, 490, 64, "purple", "Managed system",
             ["transport · Rancher domain · Ericsson core"], tsize=19))
b.append(box(120, 205, 490, 64, "purple", "OTel gateway",
             ["tee: two independent export queues"], tsize=19))
b.append(box(120, 295, 490, 64, "purple", "Elasticsearch production",
             ["live index + alarm history"], tsize=19))
b.append(box(120, 385, 490, 64, "amber", "EDA + AWX — armed rules",
             ["real actions, human approval"], tsize=19))
b.append(box(120, 475, 490, 64, "purple", "Production assets",
             ["fallback plans applied"], tsize=19))
b.append(arrow([(365, 179), (365, 203)]))
b.append(arrow([(365, 269), (365, 293)]))
b.append(arrow([(365, 359), (365, 383)]))
b.append(arrow([(365, 449), (365, 473)]))

b.append(zone(730, 60, 610, 520, "Pre-production zone — shadow, log only", "teal"))
b.append(box(790, 115, 490, 64, "teal", "Speed layer — live tap",
             ["real alarms, filtered and pseudonymized"], tsize=19))
b.append(box(790, 205, 490, 64, "teal", "Batch layer — history replay",
             ["past incidents replayed on demand"], tsize=19))
b.append(box(790, 295, 490, 64, "teal", "Elasticsearch pre-production",
             ["candidate rules evaluated"], tsize=19))
b.append(box(790, 385, 490, 64, "teal", "EDA + AWX — shadow",
             ["log only, no action possible"], tsize=19))
b.append(box(790, 475, 490, 64, "teal", "Would-have-triggered report",
             ["false positives, coverage, metrics"], tsize=19))
b.append(arrow([(1280, 147), (1320, 147), (1320, 327), (1284, 327)]))
b.append(arrow([(1035, 269), (1035, 293)]))
b.append(arrow([(1035, 359), (1035, 383)]))
b.append(arrow([(1035, 449), (1035, 473)]))
b.append(arrow([(610, 225), (690, 225), (690, 147), (788, 147)], dashed=True))
b.append(label(700, 130, "tap", 14))
b.append(arrow([(610, 327), (730, 327), (730, 237), (788, 237)], dashed=True))
b.append(label(742, 290, "replay", 14, "start"))

b.append(box(430, 650, 540, 70, "purple", "Git — rule promotion (merge request)",
             ["shadow directory  →  production directory"], tsize=19))
b.append(arrow([(1035, 539), (1035, 685), (972, 685)]))
b.append(arrow([(428, 685), (90, 685), (90, 417), (118, 417)]))
b.append(label(700, 745, "Exit criteria: false-positive rate, coverage of known incidents, zero unwanted trigger", 15))
b.append(label(1035, 560, "No credentials and no network route towards production", 15, "middle",
               COL["teal"]["title"], True))
svg(1400, 790, "\n".join(b), "/home/claude/archi/v2_lambda_view.svg")
print("Figures 6 and 7 generated.")

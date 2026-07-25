#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.2 diagrams: local CPU inference, SUSE Observability (infra) + Elastic (service)."""
import importlib.util

spec = importlib.util.spec_from_file_location("db", "/home/claude/archi/diagram_base.py")
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)
box, zone, arrow, label, num, svg = db.box, db.zone, db.arrow, db.label, db.num, db.svg
COL, TXT, TXT2, ARROW = db.COL, db.TXT, db.TXT2, db.ARROW


def plain(pts, width=1.8, dashed=False):
    d = "M" + " L".join(f"{p[0]} {p[1]}" for p in pts)
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    return f'<path d="{d}" fill="none" stroke="{ARROW}" stroke-width="{width}"{dash}/>'


# ============================================================ HOSTING DOMAINS
b = []
b.append(zone(60, 60, 1280, 240, "SUSE Rancher domain — operated by the project", "purple"))
b.append(box(100, 130, 280, 130, "purple", "Management cluster",
             ["Nautobot, AWX, EDA,", "Elastic, SUSE Observability", "Own storage and ENM path"], tsize=19, ssize=14))
b.append(box(420, 130, 280, 130, "purple", "MCX workload clusters",
             ["MCPTT, MCData, MCVideo", "Deployed by Rancher Fleet"], tsize=19, ssize=14))
b.append(box(740, 130, 280, 130, "purple", "Shadow cluster",
             ["Rule validation, log only", "No route to production"], tsize=19, ssize=14))
b.append(box(1060, 130, 280, 130, "amber", "AI node pool (CPU)",
             ["Local inference, air-gapped", "Optional, not critical path"], tsize=19, ssize=14))
b.append(arrow([(380, 195), (418, 195)]))
b.append(label(399, 177, "Fleet", 14))
b.append(arrow([(700, 195), (738, 195)], dashed=True))
b.append(label(719, 177, "tap", 14))
b.append(arrow([(1058, 195), (1022, 195)], dashed=True))
b.append(arrow([(200, 300), (200, 458)]))
b.append(label(212, 350, "ENM NBI (HTTPS)", 15, "start", TXT, True))
b.append(arrow([(330, 458), (330, 302)]))
b.append(label(342, 420, "FM / PM feeds", 15, "start", TXT, True))
b.append(arrow([(430, 300), (430, 380), (1100, 380), (1100, 458)]))
b.append(label(765, 368, "NETCONF / SSH", 15, "middle", TXT, True))
b.append(zone(60, 460, 760, 240, "Ericsson dedicated infrastructure — vendor-operated", "gray"))
b.append(box(100, 520, 680, 70, "gray", "Ericsson Network Manager (ENM)",
             ["Configuration and alarm northbound interfaces"]))
b.append(box(100, 610, 680, 70, "gray", "Core network functions on Ericsson platform",
             ["Vendor-managed lifecycle — no third-party agents"]))
b.append(zone(860, 460, 480, 240, "Transport domain", "teal"))
b.append(box(900, 520, 400, 70, "teal", "IP transport", ["Routers, switches, firewalls"]))
b.append(label(1100, 635, "Underlay shared by both hosting domains", 15))
b.append(label(1100, 660, "Managed directly over NETCONF/YANG", 15))
svg(1400, 740, "\n".join(b), "/home/claude/archi/v4_hosting_domains.svg")

# ============================================================ PHYSICAL
b = []
b.append(zone(60, 60, 820, 390, "Rancher — management cluster (dedicated)", "purple"))
b.append(box(100, 115, 230, 85, "purple", "Git + CI/CD", ["repos, pipelines"], tsize=18))
b.append(box(365, 115, 230, 85, "purple", "AWX", ["orchestration, RBAC"], tsize=18))
b.append(box(630, 115, 230, 85, "purple", "EDA", ["rulebooks"], tsize=18))
b.append(box(100, 225, 230, 85, "purple", "Nautobot", ["SoT, Golden Config"], tsize=18))
b.append(box(365, 225, 230, 85, "purple", "Elasticsearch", ["service plane"], tsize=18))
b.append(box(630, 225, 230, 85, "purple", "OTel gateway", ["routing, tee"], tsize=18))
b.append(box(365, 335, 230, 85, "amber", "SUSE Observability", ["infrastructure plane"], tsize=17))
b.append(box(630, 335, 230, 85, "amber", "Liz agent", ["MCP servers"], tsize=17))
b.append(arrow([(330, 157), (363, 157)]))
b.append(arrow([(630, 157), (597, 157)]))
b.append(arrow([(630, 267), (597, 267)]))
b.append(arrow([(215, 225), (215, 213), (430, 213), (430, 202)]))
b.append(arrow([(480, 225), (480, 213), (745, 213), (745, 202)]))
b.append(arrow([(680, 335), (680, 322), (480, 322), (480, 333)]))
b.append(zone(940, 60, 400, 140, "ServiceNow (SaaS)", "gray"))
b.append(box(980, 115, 320, 60, "gray", "ServiceNow", ["TSM · SOMT · TNI · CMDB"], tsize=18))
b.append(arrow([(882, 157), (978, 157)], both=True))
b.append(label(930, 140, "HTTPS", 14))
b.append(zone(940, 220, 400, 150, "Rancher — shadow cluster", "teal"))
b.append(box(980, 262, 320, 44, "teal", "Elasticsearch pre-prod", [], tsize=17))
b.append(box(980, 312, 320, 44, "teal", "EDA + AWX shadow", [], tsize=17))
b.append(arrow([(862, 267), (978, 284)], dashed=True))
b.append(label(920, 250, "tap", 14))
b.append(zone(940, 390, 400, 130, "Rancher — AI node pool (CPU)", "amber"))
b.append(box(980, 435, 320, 60, "amber", "Local inference", ["Ollama, small model"], tsize=18))
b.append(arrow([(862, 377), (900, 377), (900, 465), (978, 465)]))
b.append(zone(60, 560, 280, 200, "Transport", "teal"))
b.append(box(100, 620, 200, 70, "teal", "IP transport", ["NETCONF/YANG"], tsize=18))
b.append(zone(380, 560, 480, 200, "Rancher — MCX workload clusters", "purple"))
b.append(box(420, 620, 400, 60, "purple", "MCX applications", ["MCPTT, MCData, MCVideo"], tsize=18))
b.append(box(420, 692, 400, 58, "purple", "EDOT agents", ["DaemonSet per cluster"], tsize=18))
b.append(zone(900, 560, 440, 200, "Ericsson dedicated infrastructure", "gray"))
b.append(box(940, 620, 360, 60, "gray", "ENM", ["CM and FM northbound"], tsize=18))
b.append(box(940, 692, 360, 58, "gray", "Core NFs", ["no third-party agents"], tsize=18))
b.append(arrow([(200, 450), (200, 558)]))
b.append(label(212, 500, "NETCONF/SSH 830", 15, "start", TXT, True))
b.append(arrow([(450, 450), (450, 558)]))
b.append(label(462, 530, "Fleet GitOps 443", 15, "start", TXT, True))
b.append(arrow([(620, 558), (620, 452)]))
b.append(label(632, 500, "OTLP 4317", 15, "start", TXT, True))
b.append(arrow([(760, 450), (760, 545), (1000, 545), (1000, 558)]))
b.append(label(880, 537, "ENM NBI 443", 15, "middle", TXT, True))
b.append(arrow([(1080, 558), (1080, 530), (820, 530), (820, 452)]))
b.append(label(950, 522, "FM / PM feeds", 15, "middle", TXT, True))
svg(1400, 800, "\n".join(b), "/home/claude/archi/v4_physical_view.svg")

# ============================================================ SOFTWARE
b = []


def layer(y, name, chips, zc, cc):
    parts = [zone(60, y, 1280, 130, name, zc)]
    n = len(chips)
    gap = 22
    w = (1200 - (n - 1) * gap) / n
    for i, (t, s) in enumerate(chips):
        x = 100 + i * (w + gap)
        parts.append(box(x, y + 50, w, 62, cc, t, [s] if s else [], tsize=15, ssize=12))
    return "\n".join(parts)


b.append(layer(50, "User interfaces", [
    ("AWX Web UI", "buttons, approvals"),
    ("Nautobot UI", "Job Buttons, inventory"),
    ("Kibana", "service dashboards"),
    ("SUSE Observability UI", "platform topology"),
    ("ServiceNow", "TSM, SOMT, TNI"),
    ("Rancher UI + Liz", "assistant chat"),
], "gray", "gray"))
b.append(layer(210, "Automation applications", [
    ("Nautobot", "+ Golden Config, SSoT"),
    ("AWX", "K8s operator"),
    ("EDA Controller", "ansible-rulebook"),
    ("GitLab CI", "or equivalent"),
    ("Rancher Fleet", "GitOps engine"),
], "purple", "purple"))
b.append(layer(370, "AI assistance (advisory only)", [
    ("Liz supervisor + agents", "AIAgentConfig in Git"),
    ("Rancher MCP", "read-only mode in RUN"),
    ("Observability MCP", "infrastructure plane"),
    ("Telco MCP (custom)", "service plane, read tools"),
    ("Ollama", "local CPU inference"),
], "amber", "amber"))
b.append(layer(530, "Engines and connectors", [
    ("Ansible + collections", "netcommon, servicenow.itsm"),
    ("Nornir + scrapli_netconf", "NETCONF transport"),
    ("ENM NBI connector", "Python, REST / bulk CM"),
    ("Helm charts, Fleet bundles", "MCX and services"),
], "teal", "teal"))
b.append(layer(690, "Data and repositories", [
    ("PostgreSQL", "Nautobot, AWX"),
    ("Redis", "cache, queues"),
    ("Elasticsearch Enterprise", "service plane, history"),
    ("SUSE Observability store", "infrastructure plane"),
    ("Git repositories", "configs, rules, plans"),
    ("Vault", "secrets, rotation"),
], "gray", "gray"))
b.append(layer(850, "Collection and transport", [
    ("EDOT collector (agent)", "hosts, clusters, MCX"),
    ("OTel gateway", "routing, filtering, tee"),
    ("Syslog / SNMP / NBI receivers", "vendor normalization"),
], "coral", "coral"))
b.append(layer(1010, "Hosting platforms", [
    ("Rancher management cluster", "RKE2, dedicated storage"),
    ("Rancher workload clusters", "MCX and other services"),
    ("Rancher shadow cluster", "isolated pre-production"),
    ("Rancher AI node pool", "CPU inference"),
    ("Ericsson platform", "vendor-operated, closed"),
], "amber", "amber"))
svg(1400, 1180, "\n".join(b), "/home/claude/archi/v4_software_view.svg")

# ============================================================ AI VIEW
b = []
b.append(zone(60, 60, 620, 290, "BUILD — pre-production", "teal"))
b.append(box(100, 110, 540, 80, "teal", "Engineers",
             ["read-write agents on pre-production clusters"], tsize=19))
b.append(box(100, 230, 540, 90, "teal", "Liz + agents",
             ["Fleet · Provisioning · Application Collection · Security"], tsize=19))
b.append(arrow([(370, 190), (370, 228)]))
b.append(zone(720, 60, 620, 290, "RUN — production", "amber"))
b.append(box(760, 110, 540, 80, "amber", "Operators (Liz role, RBAC scoped)",
             ["read-only tools, human validation"], tsize=19))
b.append(box(760, 230, 540, 90, "amber", "Liz + agents",
             ["Rancher · Fleet · Observability · Telco — read only"], tsize=19))
b.append(arrow([(1030, 190), (1030, 228)]))
b.append(arrow([(450, 320), (450, 398)], both=True))
b.append(arrow([(950, 320), (950, 398)], both=True))
b.append(box(380, 400, 640, 80, "purple", "Local inference — dedicated CPU node pool",
             ["air-gapped: no prompt and no result leaves the platform"], tsize=19))
b.append(arrow([(200, 320), (200, 558)]))
b.append(plain([(1200, 320), (1200, 530), (560, 530)]))
b.append(arrow([(880, 530), (880, 558)]))
b.append(arrow([(560, 530), (560, 558)]))
b.append(box(100, 560, 280, 56, "gray", "Rancher MCP", ["read-only in RUN"], tsize=18))
b.append(box(420, 560, 280, 56, "gray", "Observability MCP", ["infrastructure plane"], tsize=18))
b.append(box(740, 560, 280, 56, "teal", "Telco MCP (custom)", ["service plane, read"], tsize=18))
b.append(box(1060, 560, 280, 56, "amber", "AWX + approval", ["the only write path"], tsize=18))
b.append(arrow([(1020, 588), (1058, 588)], dashed=True))
b.append(label(1039, 570, "prepare", 13))
b.append(arrow([(240, 616), (240, 668)]))
b.append(arrow([(560, 616), (560, 668)]))
b.append(arrow([(880, 616), (880, 668)]))
b.append(box(100, 670, 280, 56, "gray", "Rancher and K8s API", [], tsize=18))
b.append(box(420, 670, 280, 56, "gray", "SUSE Observability", ["clusters, nodes"], tsize=18))
b.append(box(740, 670, 280, 56, "teal", "Elastic, Nautobot, AWX", ["telco and MCX"], tsize=18))
svg(1400, 770, "\n".join(b), "/home/claude/archi/v4_ai_view.svg")

# ============================================================ FUNCTIONAL (F12 label)
src = open("/home/claude/archi/v3_functional_view.svg").read()
src = src.replace("Liz supervisor and agents · read-only MCP tools · prepares, never executes",
                  "Liz supervisor and agents · local inference · read-only MCP tools · prepares, never executes")
open("/home/claude/archi/v4_functional_view.svg", "w").write(src)
import cairosvg
cairosvg.svg2png(url="/home/claude/archi/v4_functional_view.svg",
                 write_to="/home/claude/archi/v4_functional_view.png", scale=2.0)
print("OK /home/claude/archi/v4_functional_view.svg")
print("v1.2 diagrams generated.")

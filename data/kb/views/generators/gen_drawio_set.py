#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full v1.1 drawio set: 8 pages, English."""
import importlib.util

spec = importlib.util.spec_from_file_location("base", "/home/claude/archi/drawio_base.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
Page, COL = base.Page, base.COL

pages = []

# ---------------------------------------------------- 1. CONCEPTUAL
P = Page("1 - Conceptual view", 1400, 800)
sot = P.box(100, 80, 360, 120, "purple", "Source of truth",
            ["Intended configs, fallback plans,", "rules — versioned in Git"])
gov = P.box(520, 80, 360, 120, "gray", "Governance (ServiceNow)",
            ["TSM, SOMT, TNI, CMDB —", "orders, incidents, approvals"])
dec = P.box(940, 80, 360, 120, "amber", "Supervised decision",
            ["Alarm correlation,", "human approval (buttons)"])
aut = P.box(100, 330, 360, 120, "purple", "Automation chain",
            ["CI validation, orchestration,", "controlled execution (RBAC)"])
obs = P.box(940, 330, 360, 120, "coral", "Observation",
            ["Service plane: Elasticsearch", "Infrastructure: SUSE Observability"])
sysg = P.box(320, 600, 760, 120, "teal", "Managed system",
             ["IP transport · Rancher domain (MCX, services) · Ericsson core (ENM)"])
P.edge(sot, aut, (280, 200), (280, 330))
P.edge(aut, sysg, (280, 450), (320, 660), pts=[(280, 660)])
P.edge(sysg, obs, (1080, 660), (1120, 450), pts=[(1120, 660)])
P.edge(obs, dec, (1120, 330), (1120, 200))
P.edge(dec, aut, (1030, 200), (380, 330), pts=[(1030, 265), (380, 265)])
P.edge(gov, dec, (880, 140), (940, 140), dashed=True, both=True)
P.edge(gov, aut, (700, 200), (420, 330), pts=[(700, 240), (420, 240)], label="orders, changes")
P.text(150, 528, 300, "Change loop (GitOps)", 12, True, COL["purple"][2], "left")
P.text(555, 278, 300, "Supervised remediation loop", 12, True, COL["amber"][2])
P.text(1135, 528, 220, "Observation loop", 12, True, COL["coral"][2], "left")
pages.append(P)

# ---------------------------------------------------- 2. FUNCTIONAL
P = Page("2 - Functional view", 1400, 1190)
H = 110
f1 = P.box(60, 80, 280, H, "purple", "F1 · Configuration repository",
           ["Templates, plans, rules", "versioned in Git"], 12)
f2 = P.box(60, 240, 280, H, "purple", "F2 · Network source of truth",
           ["Inventory, assets,", "per-device data"], 12)
f10 = P.box(60, 400, 280, H, "purple", "F10 · Compliance & drift",
            ["Intended vs actual,", "compliance reports"], 12)
f3 = P.box(380, 80, 300, H, "teal", "F3 · CI validation",
           ["Lint, rendering, tests,", "fallback-plan checks"], 12)
f4 = P.box(380, 240, 300, H, "teal", "F4 · Orchestration",
           ["Buttons, RBAC,", "approval workflows"], 12)
f5 = P.box(380, 400, 300, H, "teal", "F5 · Southbound connectors",
           ["NETCONF · Fleet · ENM NBI"], 12)
sg = P.box(380, 560, 300, H, "gray", "Managed system",
           ["Transport, Rancher domain,", "Ericsson core"], 12)
f9 = P.box(720, 80, 300, H, "gray", "F9 · ITSM / inventory",
           ["TSM, SOMT, TNI, CMDB"], 12)
f8 = P.box(720, 240, 300, H, "coral", "F8 · Event-driven decision",
           ["Rulebooks: alarm →", "workflow mapping"], 12)
f7 = P.box(720, 400, 300, H, "coral", "F7 · Service analytics",
           ["Elasticsearch: telco and MCX", "signals, correlation, alerting"], 12)
f6 = P.box(720, 560, 300, H, "coral", "F6 · Collection & routing",
           ["EDOT agents, gateway,", "attribute-based routing"], 12)
f11 = P.box(1060, 400, 280, H, "amber", "F11 · Infra observability",
            ["SUSE Observability:", "clusters, nodes, storage"], 12)
f12 = P.box(60, 720, 1280, 90, "purple", "F12 · AI assistance (advisory)",
            ["Liz supervisor and agents · local inference · read-only MCP tools · prepares, never executes"], 13)
P.edge(f1, f3, (340, 135), (380, 135)); P.badge(359, 112, 1)
P.edge(f2, f4, (340, 295), (380, 295)); P.badge(359, 272, 2)
P.edge(f3, f4, (530, 190), (530, 240)); P.badge(560, 216, 3)
P.edge(f4, f5, (530, 350), (530, 400)); P.badge(560, 376, 4)
P.edge(f5, sg, (530, 510), (530, 560)); P.badge(560, 536, 5)
P.edge(sg, f6, (680, 615), (720, 615)); P.badge(699, 592, 6)
P.edge(f6, f7, (870, 560), (870, 510)); P.badge(900, 537, 7)
P.edge(f6, f11, (1020, 590), (1200, 510), pts=[(1200, 590)]); P.badge(1110, 590, 8)
P.edge(f11, f7, (1060, 455), (1020, 455)); P.badge(1041, 432, 9)
P.edge(f7, f8, (870, 400), (870, 350)); P.badge(900, 377, 10)
P.edge(f8, f4, (720, 295), (680, 295)); P.badge(700, 272, 11)
P.edge(f8, f9, (870, 240), (870, 190)); P.badge(900, 217, 12)
P.edge(f9, f4, (760, 190), (620, 240), pts=[(760, 215), (620, 215)]); P.badge(690, 215, 13)
P.edge(f2, f9, (340, 265), (900, 80), pts=[(360, 265), (360, 40), (900, 40)],
       dashed=True, both=True); P.badge(630, 40, 14)
P.edge(f5, f10, (380, 455), (340, 455)); P.badge(360, 432, 15)
P.edge(f12, f10, (150, 720), (150, 510), dashed=True); P.badge(150, 610, 16)
P.edge(f12, f7, (700, 720), (720, 455), pts=[(700, 455)], dashed=True); P.badge(700, 640, 16)
P.edge(f12, f11, (1200, 720), (1200, 510), dashed=True); P.badge(1200, 610, 16)
P.edge(f12, f4, (355, 720), (380, 295), pts=[(355, 295)], dashed=True); P.badge(355, 610, 17)
leg = [
    "Commit triggers CI validation",
    "Inventory and data provided to orchestration",
    "Validated deployment handed to orchestration",
    "Job launch towards the connectors",
    "Configuration application (per domain)",
    "Telemetry, logs and alarms collected",
    "Service and MCX signals routed to Elasticsearch",
    "Infrastructure signals routed to SUSE Observability",
    "Infrastructure health events forwarded for correlation",
    "Qualified alarm to event-driven decision",
    "Workflow triggered, subject to approval",
    "Incident and change creation, updates",
    "Service order tasks (SOMT) handed to orchestration",
    "Inventory synchronization towards CMDB and TNI",
    "Actual configurations (backups) for drift",
    "Read-only context for the assistant",
    "Prepared action — executed only after approval",
]
for i, t in enumerate(leg):
    cx = 100 + (i // 9) * 660
    cy = 860 + (i % 9) * 32
    P.badge(cx, cy, i + 1)
    P.text(cx + 20, cy - 12, 520, t, 11, False, "#2C2C2A", "left")
pages.append(P)

# ---------------------------------------------------- 3. HOSTING DOMAINS
P = Page("3 - Hosting domains", 1400, 740)
P.zone(60, 60, 1280, 240, "SUSE Rancher domain — operated by the project", "purple")
mgmt = P.box(100, 130, 280, 130, "purple", "Management cluster",
             ["Nautobot, AWX, EDA, Elastic,", "SUSE Observability", "Own storage and ENM path"])
mcx = P.box(420, 130, 280, 130, "purple", "MCX workload clusters",
            ["MCPTT, MCData, MCVideo", "Deployed by Rancher Fleet"])
shad = P.box(740, 130, 280, 130, "purple", "Shadow cluster",
             ["Rule validation, log only", "No route to production"])
aipool = P.box(1060, 130, 280, 130, "amber", "AI node pool (CPU)",
               ["Local inference, air-gapped", "Optional, not critical path"])
P.edge(mgmt, mcx, (380, 195), (420, 195), label="Fleet")
P.edge(mcx, shad, (700, 195), (740, 195), dashed=True, label="tap")
P.edge(aipool, shad, (1060, 195), (1020, 195), dashed=True)
P.zone(60, 450, 760, 240, "Ericsson dedicated infrastructure — vendor-operated", "gray")
enm = P.box(100, 510, 680, 70, "gray", "Ericsson Network Manager (ENM)",
            ["Configuration and alarm northbound interfaces"])
nfs = P.box(100, 600, 680, 70, "gray", "Core network functions on Ericsson platform",
            ["Vendor-managed lifecycle — no third-party agents"])
P.zone(860, 450, 480, 240, "Transport domain", "teal")
tra = P.box(900, 510, 400, 70, "teal", "IP transport", ["Routers, switches, firewalls"])
P.edge(mgmt, enm, (200, 260), (200, 510), label="ENM NBI (HTTPS)")
P.edge(enm, mgmt, (330, 510), (330, 260), label="FM / PM feeds")
P.edge(mgmt, tra, (300, 260), (1100, 510), pts=[(300, 380), (1100, 380)], label="NETCONF / SSH")
P.text(900, 610, 400, "Underlay shared by both hosting domains", 11, False, "#5F5E5A")
pages.append(P)

# ---------------------------------------------------- 4. PHYSICAL
P = Page("4 - Physical view and flows", 1400, 820)
P.zone(60, 60, 820, 390, "Rancher — management cluster (dedicated)", "purple")
git = P.box(100, 115, 230, 85, "purple", "Git + CI/CD", ["repos, pipelines"], 13)
awx = P.box(365, 115, 230, 85, "purple", "AWX", ["orchestration, RBAC"], 13)
eda = P.box(630, 115, 230, 85, "purple", "EDA", ["rulebooks"], 13)
nau = P.box(100, 225, 230, 85, "purple", "Nautobot", ["SoT, Golden Config"], 13)
ela = P.box(365, 225, 230, 85, "purple", "Elasticsearch", ["service plane"], 13)
gwo = P.box(630, 225, 230, 85, "purple", "OTel gateway", ["routing, tee"], 13)
sob = P.box(365, 335, 230, 85, "amber", "SUSE Observability", ["infrastructure plane"], 12)
liz = P.box(630, 335, 230, 85, "amber", "Liz agent", ["MCP servers"], 12)
P.edge(git, awx, (330, 157), (365, 157))
P.edge(eda, awx, (630, 157), (595, 157))
P.edge(gwo, ela, (630, 267), (595, 267))
P.edge(nau, awx, (215, 225), (430, 200), pts=[(215, 213), (430, 213)])
P.edge(ela, eda, (480, 225), (745, 200), pts=[(480, 213), (745, 213)])
P.edge(gwo, sob, (680, 335), (480, 335), pts=[(680, 322), (480, 322)])
P.zone(940, 60, 400, 140, "ServiceNow (SaaS)", "gray")
snw = P.box(980, 115, 320, 60, "gray", "ServiceNow", ["TSM · SOMT · TNI · CMDB"], 13)
P.edge(eda, snw, (860, 157), (980, 157), both=True, label="HTTPS 443")
P.zone(940, 220, 400, 150, "Rancher — shadow cluster", "teal")
epp = P.box(980, 262, 320, 44, "teal", "Elasticsearch pre-prod", [], 13)
osh = P.box(980, 312, 320, 44, "teal", "EDA + AWX shadow", [], 13)
P.zone(940, 390, 400, 130, "Rancher — AI node pool (CPU)", "amber")
inf = P.box(980, 435, 320, 60, "amber", "Local inference", ["Ollama, small model"], 13)
P.edge(gwo, epp, (860, 267), (980, 284), dashed=True, label="tap (OTLP)")
P.edge(liz, inf, (860, 377), (980, 465), pts=[(900, 377), (900, 465)])
P.zone(60, 560, 280, 200, "Transport", "teal")
tra = P.box(100, 620, 200, 70, "teal", "IP transport", ["NETCONF/YANG"], 13)
P.zone(380, 560, 480, 200, "Rancher — MCX workload clusters", "purple")
mcxa = P.box(420, 620, 400, 60, "purple", "MCX applications", ["MCPTT, MCData, MCVideo"], 13)
edot = P.box(420, 692, 400, 58, "purple", "EDOT agents", ["DaemonSet per cluster"], 13)
P.zone(900, 560, 440, 200, "Ericsson dedicated infrastructure", "gray")
enm2 = P.box(940, 620, 360, 60, "gray", "ENM", ["CM and FM northbound"], 13)
nfs2 = P.box(940, 692, 360, 58, "gray", "Core NFs", ["no third-party agents"], 13)
P.edge(awx, tra, (365, 157), (200, 620), pts=[(200, 157)], label="NETCONF/SSH 830")
P.edge(git, mcxa, (215, 200), (450, 620), pts=[(215, 500), (450, 500)], label="Fleet GitOps 443")
P.edge(edot, gwo, (620, 692), (700, 310), pts=[(620, 530), (700, 530)], label="OTLP 4317")
P.edge(awx, enm2, (480, 200), (1000, 620), pts=[(480, 545), (1000, 545)], label="ENM NBI 443")
P.edge(enm2, gwo, (1080, 620), (790, 310), pts=[(1080, 530), (790, 530)], label="FM / PM feeds")
pages.append(P)

# ---------------------------------------------------- 5. SOFTWARE
P = Page("5 - Software view", 1400, 1200)


def layer(y, name, chips, zc, cc):
    P.zone(60, y, 1280, 130, name, zc)
    n = len(chips)
    gap = 22
    w = (1200 - (n - 1) * gap) / n
    for i, (t, s) in enumerate(chips):
        x = 100 + i * (w + gap)
        P.box(round(x), y + 50, round(w), 62, cc, t, [s] if s else [], 11, 10)


layer(50, "User interfaces", [
    ("AWX Web UI", "buttons, approvals"),
    ("Nautobot UI", "Job Buttons, inventory"),
    ("Kibana", "service dashboards"),
    ("SUSE Observability UI", "platform topology"),
    ("ServiceNow", "TSM, SOMT, TNI"),
    ("Rancher UI + Liz", "assistant chat"),
], "gray", "gray")
layer(210, "Automation applications", [
    ("Nautobot", "+ Golden Config, SSoT"),
    ("AWX", "K8s operator"),
    ("EDA Controller", "ansible-rulebook"),
    ("GitLab CI", "or equivalent"),
    ("Rancher Fleet", "GitOps engine"),
], "purple", "purple")
layer(370, "AI assistance (advisory only)", [
    ("Liz supervisor + agents", "AIAgentConfig in Git"),
    ("Rancher MCP", "read-only mode in RUN"),
    ("Observability MCP", "infrastructure plane"),
    ("Telco MCP (custom)", "service plane, read tools"),
    ("Ollama", "local CPU inference"),
], "amber", "amber")
layer(530, "Engines and connectors", [
    ("Ansible + collections", "netcommon, servicenow.itsm"),
    ("Nornir + scrapli_netconf", "NETCONF transport"),
    ("ENM NBI connector", "Python, REST / bulk CM"),
    ("Helm charts, Fleet bundles", "MCX and services"),
], "teal", "teal")
layer(690, "Data and repositories", [
    ("PostgreSQL", "Nautobot, AWX"),
    ("Redis", "cache, queues"),
    ("Elasticsearch Enterprise", "service plane, history"),
    ("SUSE Observability store", "infrastructure plane"),
    ("Git repositories", "configs, rules, plans"),
    ("Vault", "secrets, rotation"),
], "gray", "gray")
layer(850, "Collection and transport", [
    ("EDOT collector (agent)", "hosts, clusters, MCX"),
    ("OTel gateway", "routing, filtering, tee"),
    ("Syslog / SNMP / NBI receivers", "vendor normalization"),
], "coral", "coral")
layer(1010, "Hosting platforms", [
    ("Rancher management cluster", "RKE2, dedicated storage"),
    ("Rancher workload clusters", "MCX and other services"),
    ("Rancher shadow cluster", "isolated pre-production"),
    ("Rancher AI node pool", "CPU inference"),
    ("Ericsson platform", "vendor-operated, closed"),
], "amber", "amber")
pages.append(P)

# ---------------------------------------------------- 6. DEPLOYMENT
P = Page("6 - Deployment view", 1400, 1060)
P.zone(60, 50, 1280, 510, "A · Deployment of telemetry collection and routing", "coral")
gitfleet = P.box(100, 100, 560, 64, "purple", "Git  →  Rancher Fleet",
                 ["Agent and gateway configuration deployed as bundles"], 13)
c1 = P.box(100, 200, 240, 80, "purple", "Management cluster", ["EDOT agent (DaemonSet)"], 13)
c2 = P.box(420, 200, 240, 80, "purple", "MCX workload clusters", ["EDOT agent (DaemonSet)"], 13)
s1 = P.box(740, 200, 240, 80, "gray", "Ericsson ENM", ["FM / PM feeds — no agent"], 13)
s2 = P.box(1060, 200, 240, 80, "teal", "Transport devices", ["syslog, SNMP — no agent"], 13)
gw = P.box(470, 350, 460, 80, "coral", "OTel gateway collectors",
           ["receivers · filtering · pseudonymization", "attribute-based routing and tee"], 13)
esp = P.box(100, 470, 380, 60, "coral", "Elasticsearch", ["telco and MCX service plane"], 13)
sobs = P.box(520, 470, 380, 60, "amber", "SUSE Observability", ["infrastructure plane"], 13)
esq = P.box(940, 470, 380, 60, "teal", "Elasticsearch pre-prod", ["shadow validation"], 13)
P.edge(gitfleet, c1, (220, 164), (220, 200))
P.edge(gitfleet, c2, (540, 164), (540, 200))
P.edge(c1, gw, (220, 280), (600, 350), pts=[(220, 315), (600, 315)])
P.edge(c2, gw, (540, 280), (640, 350), pts=[(540, 315), (640, 315)])
P.edge(s1, gw, (860, 280), (760, 350), pts=[(860, 315), (760, 315)])
P.edge(s2, gw, (1180, 280), (820, 350), pts=[(1180, 315), (820, 315)])
P.edge(gw, esp, (600, 430), (290, 470), pts=[(600, 452), (290, 452)], label="service signals")
P.edge(gw, sobs, (710, 430), (710, 470), label="infrastructure")
P.edge(gw, esq, (870, 430), (1130, 470), pts=[(870, 452), (1130, 452)], dashed=True, label="tap")
P.zone(60, 600, 1280, 400, "B · Closed-loop playbook triggered on alarm, executed on approval", "amber")
al = P.box(100, 660, 260, 80, "coral", "Alerting rule", ["Kibana / Elasticsearch"], 13)
eda2 = P.box(420, 660, 260, 80, "coral", "EDA rulebook", ["dedup, kill switch, lock"], 13)
wf = P.box(740, 660, 260, 80, "amber", "AWX workflow", ["launched with alarm context"], 13)
ap = P.box(1060, 660, 260, 80, "amber", "Approval node", ["operator button, timeout"], 13)
op = P.box(740, 770, 260, 58, "amber", "Operator-initiated action", ["same workflow and approval"], 12)
pb = P.box(1000, 850, 300, 80, "purple", "Playbook execution", ["pre-checks, apply, post-checks"], 13)
tg = P.box(600, 850, 340, 80, "purple", "Target domain", ["NETCONF · Fleet commit · ENM NBI"], 13)
sn = P.box(100, 850, 440, 80, "gray", "ServiceNow", ["incident opened, then updated"], 13)
P.edge(al, eda2, (360, 700), (420, 700))
P.edge(eda2, wf, (680, 700), (740, 700))
P.edge(wf, ap, (1000, 700), (1060, 700))
P.edge(op, wf, (870, 770), (870, 740))
P.edge(ap, pb, (1190, 740), (1190, 850))
P.edge(pb, tg, (1000, 890), (940, 890))
P.edge(tg, sn, (600, 890), (540, 890))
P.edge(eda2, sn, (560, 740), (430, 850), pts=[(560, 820), (430, 820)])
pages.append(P)

# ---------------------------------------------------- 7. LAMBDA
P = Page("7 - Lambda view (prod / pre-prod)", 1400, 810)
P.zone(60, 60, 610, 520, "Production zone — armed", "purple")
m1 = P.box(120, 115, 490, 64, "purple", "Managed system",
           ["transport · Rancher domain · Ericsson core"], 13)
m2 = P.box(120, 205, 490, 64, "purple", "OTel gateway", ["tee: two independent export queues"], 13)
m3 = P.box(120, 295, 490, 64, "purple", "Elasticsearch production", ["live index + alarm history"], 13)
m4 = P.box(120, 385, 490, 64, "amber", "EDA + AWX — armed rules", ["real actions, human approval"], 13)
m5 = P.box(120, 475, 490, 64, "purple", "Production assets", ["fallback plans applied"], 13)
P.edge(m1, m2, (365, 179), (365, 205))
P.edge(m2, m3, (365, 269), (365, 295))
P.edge(m3, m4, (365, 359), (365, 385))
P.edge(m4, m5, (365, 449), (365, 475))
P.zone(730, 60, 610, 520, "Pre-production zone — shadow, log only", "teal")
p1 = P.box(790, 115, 490, 64, "teal", "Speed layer — live tap",
           ["real alarms, filtered and pseudonymized"], 13)
p2 = P.box(790, 205, 490, 64, "teal", "Batch layer — history replay",
           ["past incidents replayed on demand"], 13)
p3 = P.box(790, 295, 490, 64, "teal", "Elasticsearch pre-production", ["candidate rules evaluated"], 13)
p4 = P.box(790, 385, 490, 64, "teal", "EDA + AWX — shadow", ["log only, no action possible"], 13)
p5 = P.box(790, 475, 490, 64, "teal", "Would-have-triggered report",
           ["false positives, coverage, metrics"], 13)
P.edge(p1, p3, (1280, 147), (1280, 327), pts=[(1320, 147), (1320, 327)])
P.edge(p2, p3, (1035, 269), (1035, 295))
P.edge(p3, p4, (1035, 359), (1035, 385))
P.edge(p4, p5, (1035, 449), (1035, 475))
P.edge(m2, p1, (610, 225), (790, 147), pts=[(690, 225), (690, 147)], dashed=True, label="tap")
P.edge(m3, p2, (610, 327), (790, 237), pts=[(730, 327), (730, 237)], dashed=True, label="replay")
gitp = P.box(430, 650, 540, 70, "purple", "Git — rule promotion (merge request)",
             ["shadow directory  →  production directory"], 13)
P.edge(p5, gitp, (1035, 539), (970, 685), pts=[(1035, 685)])
P.edge(gitp, m4, (430, 720), (120, 417), pts=[(90, 720), (90, 417)])
P.text(430, 740, 540, "Exit criteria: false-positive rate, coverage, zero unwanted trigger", 11)
P.text(790, 548, 490, "No credentials and no network route towards production", 11, True, COL["teal"][2])
pages.append(P)

# ---------------------------------------------------- 8. AI ASSISTANCE
P = Page("8 - AI assistance (BUILD / RUN)", 1400, 790)
P.zone(60, 60, 620, 290, "BUILD — pre-production", "teal")
eng = P.box(100, 110, 540, 80, "teal", "Engineers",
            ["read-write agents on pre-production clusters"], 13)
lizb = P.box(100, 230, 540, 90, "teal", "Liz + agents",
             ["Fleet · Provisioning · Application Collection · Security"], 13)
P.edge(eng, lizb, (370, 190), (370, 230))
P.zone(720, 60, 620, 290, "RUN — production", "amber")
ope = P.box(760, 110, 540, 80, "amber", "Operators (Liz role, RBAC scoped)",
            ["read-only tools, human validation"], 13)
lizr = P.box(760, 230, 540, 90, "amber", "Liz + agents",
             ["Rancher · Fleet · Observability · Telco — read only"], 13)
P.edge(ope, lizr, (1030, 190), (1030, 230))
inf = P.box(380, 400, 640, 80, "purple", "Local inference — dedicated CPU node pool",
            ["air-gapped: no prompt and no result leaves the platform"], 13)
P.edge(lizb, inf, (450, 320), (450, 400), both=True)
P.edge(lizr, inf, (950, 320), (950, 400), both=True)
mcp1 = P.box(100, 560, 280, 56, "gray", "Rancher MCP", ["read-only in RUN"], 13)
mcp2 = P.box(420, 560, 280, 56, "gray", "Observability MCP", ["infrastructure plane"], 13)
mcp3 = P.box(740, 560, 280, 56, "teal", "Telco MCP (custom)", ["service plane, read"], 13)
awxa = P.box(1060, 560, 280, 56, "amber", "AWX + approval", ["the only write path"], 13)
P.edge(lizb, mcp1, (200, 320), (200, 560))
P.edge(lizr, mcp3, (1200, 320), (880, 560), pts=[(1200, 530), (880, 530)])
P.edge(lizr, mcp2, (1200, 320), (560, 560), pts=[(1200, 530), (560, 530)])
P.edge(mcp3, awxa, (1020, 588), (1060, 588), dashed=True, label="prepare")
api1 = P.box(100, 670, 280, 56, "gray", "Rancher and K8s API", [], 13)
api2 = P.box(420, 670, 280, 56, "gray", "SUSE Observability", ["clusters, nodes"], 13)
api3 = P.box(740, 670, 280, 56, "teal", "Elastic, Nautobot, AWX", ["telco and MCX"], 13)
P.edge(mcp1, api1, (240, 616), (240, 670))
P.edge(mcp2, api2, (560, 616), (560, 670))
P.edge(mcp3, api3, (880, 616), (880, 670))
pages.append(P)

out = ('<mxfile host="app.diagrams.net" type="device">'
       + "".join(p.xml() for p in pages) + "</mxfile>")
for ext in ("drawio", "xml"):
    with open(f"/home/claude/archi/netdevops_mcx_architecture_diagrams_v1_3.{ext}", "w") as f:
        f.write(out)
print("drawio v1.2 written,", len(out), "chars,", len(pages), "pages")

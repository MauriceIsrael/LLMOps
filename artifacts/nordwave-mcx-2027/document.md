# Document d'Architecture System — Engagement nordwave-mcx-2027
**Statut du Document :** `PROVISIONAL`
**Conflits Ouverts :** 0

---
## Sections Rédigées

### Section 4.1

- Énoncé validé (`designed`) par Amina Duarte : `is_constrained_by` = `floor arbitration terminates in the MC service layer at the site`.
  > *Verbatim :* "The MCX layer delivers group voice, data and video to dispatchers and field
teams, and it has to keep delivering group voice when almost nothing else works.
Our boundary is the 3GPP MC service layer: group and affiliation management,
floor control, media distribution, and the interworking function towards the
legacy LMR fleet, which stays for four more years. Everything below - bearers,
QoS, slices - belongs to the core team.

What must survive is talkgroup communication inside an isolated site: if the
transport to the national data centres is cut, a site must keep serving its
local talkgroups. That is a hard requirement from the customer, and I do not yet
know whether the platform we shortlist can do it without a local instance."
- Énoncé validé (`stated-by-client`) par Amina Duarte : `has_property` = `group voice must survive site isolation from national data centres`.
  > *Verbatim :* "The MCX layer delivers group voice, data and video to dispatchers and field
teams, and it has to keep delivering group voice when almost nothing else works.
Our boundary is the 3GPP MC service layer: group and affiliation management,
floor control, media distribution, and the interworking function towards the
legacy LMR fleet, which stays for four more years. Everything below - bearers,
QoS, slices - belongs to the core team.

What must survive is talkgroup communication inside an isolated site: if the
transport to the national data centres is cut, a site must keep serving its
local talkgroups. That is a hard requirement from the customer, and I do not yet
know whether the platform we shortlist can do it without a local instance."
- Énoncé validé (`designed`) par Amina Duarte : `decomposes_into` = `group-management, floor-control, media-distribution, lmr-interworking`.
  > *Verbatim :* "Four parts. Group and affiliation management, which is mostly a data problem and
talks to the subscriber database. Floor control, which is the latency-critical
one and the reason people will judge the system. Media distribution, where the
question is unicast versus multicast on the radio side. And the LMR interworking
function, which is a gateway to a vendor system we do not control."

### Section 5.1

- Énoncé validé (`designed`) par Rui Vasconcelos : `has_property` = `dedicated 5G standalone core, 2 sites active-active, reserved slicing`.
  > *Verbatim :* "The core is a dedicated 5G standalone core, national, two sites active-active, with slicing reserved for the mission-critical service."

### Section 4.3

- Énoncé validé (`designed`) par Rui Vasconcelos : `depends_on` = `depends on a committed priority and pre-emption profile in the core`.
  > *Verbatim :* "depends on a committed priority and pre-emption profile in the core"

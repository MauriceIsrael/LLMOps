# Document d'Architecture System — Engagement nordwave-mcx-2027
**Statut du Document :** `provisional`
**Conflits Ouverts :** 1

---
## Sections Rédigées

### Section 4.1

- Énoncé validé (`designed`) par amina : `is_constrained_by` = `3GPP MC service layer boundary`.
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
- Énoncé validé (`stated-by-client`) par amina : `has_property` = `group voice must survive site isolation from national data centres`.
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
- Énoncé validé (`designed`) par amina : `decomposes_into` = `group-management, floor-control, media-distribution, lmr-interworking`.
  > *Verbatim :* "Four parts. Group and affiliation management, which is mostly a data problem and
talks to the subscriber database. Floor control, which is the latency-critical
one and the reason people will judge the system. Media distribution, where the
question is unicast versus multicast on the radio side. And the LMR interworking
function, which is a gateway to a vendor system we do not control."

### Section 5.1

- Énoncé validé (`designed`) par rui : `has_property` = `dedicated 5G standalone core, 2 sites active-active, reserved slicing`.
  > *Verbatim :* "A dedicated 5G standalone core, national, two sites active-active, with a slice reserved for the mission-critical service."

### Section 4.3

- Énoncé validé (`designed`) par amina : `has_property` = `floor arbitration terminates in the MC service layer at the site`.
  > *Verbatim :* "arbitration terminates in the MC service layer, at the site"
- Énoncé validé (`designed`) par rui : `depends_on` = `depends on a committed priority and pre-emption profile in the core`.
  > *Verbatim :* "depends on a committed priority and pre-emption profile in the core"

### Section 4.4

- Énoncé validé (`designed`) par amina : `has_property` = `multicast on the radio side`.
  > *Verbatim :* "multicast on the radio side"
- Énoncé validé (`designed`) par rui : `has_property` = `unicast only, multicast deferred`.
  > *Verbatim :* "unicast only, multicast deferred"

### Section 4.5

- Énoncé validé (`observed`) par external:m.okonkwo : `depends_on` = `On release 23.4 the element manager's bulk configuration export is capped at
2 000 managed objects per request and rejects concurrent exports on the same
node. In practice a full export of a core node takes three passes. Anyone
planning a nightly backup of the whole estate through that interface should size
for that, and should not assume the documented figure of 10 000.`.
  > *Verbatim :* "On release 23.4 the element manager's bulk configuration export is capped at
2 000 managed objects per request and rejects concurrent exports on the same
node. In practice a full export of a core node takes three passes. Anyone
planning a nightly backup of the whole estate through that interface should size
for that, and should not assume the documented figure of 10 000."

---
## ⚠️ Registre des Conflits Ouverts

- **Conflit `C-0002`** (contradiction) : Contradiction automatique détectée entre S-0007 et S-0008 sur media-distribution (has_property)
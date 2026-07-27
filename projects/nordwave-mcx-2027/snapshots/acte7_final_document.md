# Document d'Architecture System — Engagement nordwave-mcx-2027
**Statut du Document :** `PROVISIONAL`
**Conflits Ouverts :** 1

---
## Sections Rédigées

### Section 4.1

- Énoncé validé (`designed`) par Amina Duarte : `is_constrained_by` = `3GPP MC service layer boundary`.
  > *Verbatim :* "The MCX layer delivers group voice. Boundary is 3GPP MC service layer."
- Énoncé validé (`stated-by-client`) par Amina Duarte : `has_property` = `group voice must survive site isolation from national data centres`.
  > *Verbatim :* "The MCX layer delivers group voice. Boundary is 3GPP MC service layer."
- Énoncé validé (`designed`) par Amina Duarte : `is_constrained_by` = `3GPP MC service layer boundary`.
  > *Verbatim :* ""
- Énoncé validé (`stated-by-client`) par Amina Duarte : `has_property` = `group voice must survive site isolation from national data centres`.
  > *Verbatim :* ""

### Section 4.3

- Énoncé validé (`designed`) par Amina Duarte : `has_property` = `floor arbitration terminates in the MC service layer at the site`.
  > *Verbatim :* ""
- Énoncé validé (`designed`) par Rui Vasconcelos : `depends_on` = `depends on a committed priority and pre-emption profile in the core`.
  > *Verbatim :* "depends on a committed priority and pre-emption profile in the core"

---
## ⚠️ Registre des Conflits Ouverts

- **Conflit `C-0001`** (contradiction) : Contestation de l'énoncé S-0005 par Rui Vasconcelos (mobile-core-architect) : depends on a committed priority and pre-emption profile in the core
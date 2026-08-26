# 💬 Exemple Rendu & Travaillé — Fiches Mailbox et Protocole d'Élicitation (`SPEC-MAILBOX.md`)

Ce document illustre le rendu exact des fiches Markdown (Cards) et l'interaction complète entre les experts d'architecture et la plateforme via le protocole de commandes de la boîte aux lettres (GitHub Issues / File Mailbox).

---

## 🎨 Fiche Question (Question Issue Card) — Exemple Rendu

Ci-dessous l'aperçu rendu d'une **Question Issue GitHub** générée déterministement pour la question `Q-0001` :

```markdown
<!-- elicit:demo-2026:Q-0001:question:sha=8f3a2c -->
### Quelle est la configuration de stockage du cluster de management pour la section 5.2 ?

**Why this matters**
La section 5.2 (Architecture Stockage Management) ne contient aucun énoncé. (Sections bloquées : `5.2`)

**Please use these terms**
- Sujet canonique : `Storage-5.2`
- Termes du glossaire : `Break-glass`, `Closed loop`

**Expected**
Forme attendue : decision

**Previously answered elsewhere**
Référence dans l'engagement `other-eng` : `SAN NVMe dual-controller` (Confiance : `verified`). Vous pouvez confirmer cette valeur ou vous en écarter.

**Constrained by**
- [P-012](data/kb/assets/P-012.md)
- [ADR-0011](data/kb/assets/ADR-0011.md)

**How to answer**
Copiez la commande suivante et répondez :
```
/answer Q-0001 --text "Votre réponse textuelle d'expert..."
```
```

---

## 📝 Fiche Proposition (Proposal Card)

Une fois la réponse déposée par l'expert via `/answer`, la plateforme extrait les candidats et poste la fiche de proposition **avant tout enregistrement en base** :

```markdown
<!-- elicit:demo-2026:Q-0001:proposal:sha=4d9e1a -->
### 📝 Proposition d'Énoncés d'Architecture — Question Q-0001

> **Information :** Aucun énoncé n'est encore enregistré en base. Veuillez vérifier l'extraction ci-dessous.

#### Énoncés Candidats Extraits :
- `Storage-5.2` · `has_property` · `SAN NVMe dual-controller` (Confiance : `verified`, Unité : tier-1)

#### Verbatim Exact de l'Expert :
> "Nous préconisons un SAN NVMe dual-controller tier-1."

#### Commandes Disponibles :
- **Confirmer et enregistrer :**
  `/confirm Q-0001`
- **Corriger la proposition (YAML) :**
  `/edit Q-0001`
- **Rejeter l'extraction :**
  `/reject Q-0001 Mauvaise interprétation sémantique`
```

---

## ⚠️ Fiche Conflit (Conflict Card)

Lorsqu'un second expert (Bob) propose une solution contradictoire, le système génère la fiche de conflit sans écraser l'énoncé d'Alice :

```markdown
<!-- elicit:demo-2026:C-0001:conflict:sha=1b7c3d -->
### ⚠️ Registre de Conflit d'Architecture — C-0001

**Sujet & Prédicat Contestés :** `Storage-5.2` · `has_property`
**Détail :** Contradiction décelée sur Storage-5.2 (has_property): alice propose SAN NVMe alors que bob propose Ceph HCI

#### Énoncés en Concurrence (Les deux restent actuellement actifs) :
- **Énoncé `S-001`** par alice (Rôle : `cloud-architect`) le 2026-07-26 :
  - Valeur proposée : `SAN NVMe dual-controller` (Confiance : `verified`)
  - *Verbatim :* "SAN NVMe dual-controller"
- **Énoncé `S-002`** par bob (Rôle : `storage-expert`) le 2026-07-26 :
  - Valeur proposée : `Ceph HCI all-flash SSD` (Confiance : `designed`)
  - *Verbatim :* "Ceph HCI all-flash SSD"

> 💡 **Note Consultative de Cohérence (Non contraignante) :**
> Vérifier l'impact sur le budget d'infrastructures.

#### Instruction d'Arbitrage (Architecte en chef uniquement) :
Exécutez la commande suivante en précisant obligatoirement la raison d'architecture :
```
/arbitrate keep <statement_id> --reason "Raison d'architecture expliquant la décision..."
```
```

---

## ⚖️ Fiche Arbitrage (Arbitration Card)

Lorsque Charlie (`chief-architect`) arbitre via `/arbitrate keep S-001 --reason "..."`, le système clôture le conflit et émet la fiche finale :

```markdown
<!-- elicit:demo-2026:C-0001:arbitration:sha=9e2f4a -->
### ⚖️ Rapport d'Arbitrage — Conflit C-0001

**Arbitré par :** `charlie`

#### Décision d'Architecture :
- **Énoncé Conservé (Actif) :** `S-001` (`Storage-5.2` · `has_property` = `SAN NVMe dual-controller`) par alice.
- **Énoncé Rendu Caduc (`superseded`) :** `S-002` (`Storage-5.2` · `has_property` = `Ceph HCI all-flash SSD`) par bob.

> 📌 **Note d'historique :** L'énoncé rendu caduc reste conservé dans l'historique d'architecture et constitue un candidat de promotion si l'expérience terrain le justifie ultérieurement.

#### Rationale de la Décision :
> "Homogénéité du stockage SAN avec le datacenter existant"
```

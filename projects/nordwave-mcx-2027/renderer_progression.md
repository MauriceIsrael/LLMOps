# 📑 Avancement Découplé du Document d'Architecture & Fiches Mailbox — Nordwave MCX

Ce document rassemble les sorties **réellement générées par les renderers Jinja2 et le graphe d'assemblage** du système au fil des réponses de l'équipe d'architectes.


## 🟢 Acte 1 — Premier Scan (Graphe Vierge)

### 📨 Fiche Question générée par le Question Renderer (`question.md.j2`) :
```markdown
<!-- elicit:nordwave-mcx-2027:Q-0001:question:sha=29bcc7 -->
### What is the end-to-end topology, and who operates each segment?

**Why this matters**
La section 5.1 (5.1) ne contient aucun énoncé d'architecture. (Sections bloquées : `5.1`)

**Please use these terms**
- Sujet canonique : `mcx-services`
- Termes du glossaire : `mcx-services`, `degraded-mode`
**Expected**
Forme attendue : Explicitation du périmètre et du mode dégradé


**How to answer**
Copiez la commande suivante et répondez :
```
/answer Q-0001 --text "Votre réponse textuelle d'expert..."
```
```


## 🔵 Acte 2 — Cadrage L0 -> L1 & Énoncés Validés

### 📄 Fiche Proposal générée par le Proposal Renderer (`proposal.md.j2`) :
```markdown
<!-- elicit:nordwave-mcx-2027:Q-0001:proposal:sha=66d018 -->
### 📝 Proposition d'Énoncés d'Architecture — Question Q-0001

> **Information :** Aucun énoncé n'est encore enregistré en base. Veuillez vérifier l'extraction ci-dessous.

#### Énoncés Candidats Extraits :
- `mcx-services` · `is_constrained_by` · `3GPP MC service layer boundary` (Confiance : `designed`)
- `mcx-services` · `has_property` · `group voice must survive site isolation from national data centres` (Confiance : `stated-by-client`)

#### Verbatim Exact de l'Expert :
> "The MCX layer delivers group voice. Boundary is 3GPP MC service layer."

#### Commandes Disponibles :
- **Confirmer et enregistrer :**
  `/confirm Q-0001`
- **Corriger la proposition (YAML) :**
  `/edit Q-0001`
- **Rejeter l'extraction :**
  `/reject Q-0001 Mauvaise interprétation sémantique`
```

### 📑 Document d'Architecture généré par le Renderer d'Assemblage (Acte 2) :
```markdown
# Document d'Architecture System — Engagement nordwave-mcx-2027
**Statut du Document :** `provisional`
**Conflits Ouverts :** 0

---
## Sections Rédigées

### Section 5.1

- Énoncé validé (`designed`) par amina : `has_property` = ``.
  > *Verbatim :* ""

```


## 🟣 Acte 3 — Décomposition L1 -> L2 & 4 Sujets Créés

### 📌 Maturity Board généré par le Maturity Board Renderer (`maturity_board.md.j2`) :
```markdown
<!-- elicit:nordwave-mcx-2027:maturity_board:board:sha=2316c7 -->
### 📊 Tableau de Maturité des Sujets d'Architecture (Maturity Board) — nordwave-mcx-2027

| Sujet Canonique | Niveau Atteint | Blocage / Question Ouverte | Assigné À | Délais au Niveau | Stagnation (> 7 j) | Sections Dépendantes |
|---|---|---|---|---|---|---|
| `engagement-scope` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `mcx-services` | `L2_decomposed` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `mobile-core` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `transport` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `rancher-domain` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `observation` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `automation-chain` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `service-management` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `security-posture` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `ai-assistance` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `delivery-plan` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `sim-esim-lifecycle` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `group-management` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `floor-control` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `media-distribution` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `lmr-interworking` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |

> 📌 **Règles de maturité :**
> - **L0_named** (Nommé) → **L1_framed** (Cadré) → **L2_decomposed** (Décomposé - Patterns candidats proposés) → **L3_decided** (Mécanisme décidé) → **L4_specified** (Paramétré).
> - **Section Readiness :** Une section de document ne passe en statut `COMPLETE` que si tous ses sujets dépendants ont atteint au moins le niveau `L3_decided`.
```


## 🟠 Acte 5 — Contestation & Déclenchement de Conflit Inter-Prédicats

### ⚠️ Fiche Conflit générée par le Conflict Renderer (`conflict.md.j2`) :
```markdown
<!-- elicit:nordwave-mcx-2027:C-0001:conflict:sha=dbefd2 -->
### ⚠️ Registre de Conflit d'Architecture — C-0001

**Sujet & Prédicat Contestés :** `floor-control` · `has_property / depends_on`
**Détail :** Tension inter-prédicats décelée sur floor-control (has_property vs depends_on).

#### Énoncés en Concurrence (Les deux restent actuellement actifs) :
- **Énoncé `S-0034`** par Amina Duarte (Rôle : `mcx-service-architect`) le  :
  - Valeur proposé : `arbitration terminates in the MC service layer, at the site` (Confiance : `designed`)
  - *Verbatim :* ""
- **Énoncé `S-0003`** par Rui Vasconcelos (Rôle : `mobile-core-architect`) le  :
  - Valeur proposé : `depends on a committed priority and pre-emption profile in the core` (Confiance : `designed`)
  - *Verbatim :* ""

> 💡 **Note Consultative de Cohérence (Non contraignante) :**
> Les deux positions ne sont pas exclusives. L'arbitrage est local, le profil d'admission est cœur.

#### Instruction d'Arbitrage (Architecte en chef uniquement) :
Exécutez la commande suivante en précisant obligatoirement la raison d'architecture :
```
/arbitrate keep <statement_id> --reason "Raison d'architecture expliquant la décision..."
```
```


## 🟡 Acte 6 — Arbitrage Multi-Action avec `--amend`

### ✅ Fiche Arbitrage générée par le Arbitration Renderer (`arbitration.md.j2`) :
```markdown
<!-- elicit:nordwave-mcx-2027:C-0001:arbitration:sha=d7af03 -->
### ⚖️ Rapport d'Arbitrage — Conflit C-0001

**Arbitré par :** `Sofia Lindqvist`

#### Décision d'Architecture :
- **Énoncé Conservé (Actif) :** `S-0003` (`floor-control` · `depends_on` = `depends on a committed priority and pre-emption profile in the core`) par Rui Vasconcelos.
- **Énoncé Rendu Caduc (`superseded`) :** `S-0002` (`floor-control` · `has_property` = `floor arbitration terminates in the MC service layer at the site`) par Amina Duarte.

> 📌 **Note d'historique :** L'énoncé rendu caduc reste conservé dans l'historique d'architecture et constitue un candidat de promotion si l'expérience terrain le justifie ultérieurement.

#### Rationale de la Décision :
> "Les deux sont valides. L'arbitrage est local, mais dépend du profil d'admission cœur."
```


## 📑 Acte 7 — Assemblage du Document d'Architecture Final & Board

### 📑 Document d'Architecture Assemblé par le Système (`document.md`) :
```markdown
# Document d'Architecture System — Engagement nordwave-mcx-2027
**Statut du Document :** `provisional`
**Conflits Ouverts :** 0

---
## Sections Rédigées

### Section 5.1

- Énoncé validé (`designed`) par amina : `has_property` = ``.
  > *Verbatim :* ""

### Section 4.3

- Énoncé validé (`designed`) par Amina Duarte : `has_property` = `floor arbitration terminates in the MC service layer at the site`.
  > *Verbatim :* "arbitration terminates in the MC service layer, at the site"
- Énoncé validé (`designed`) par Rui Vasconcelos : `depends_on` = `depends on a committed priority and pre-emption profile in the core`.
  > *Verbatim :* "depends on a committed priority and pre-emption profile in the core"

```

### 📌 Maturity Board Final généré par le Renderer :
```markdown
<!-- elicit:nordwave-mcx-2027:maturity_board:board:sha=95e634 -->
### 📊 Tableau de Maturité des Sujets d'Architecture (Maturity Board) — nordwave-mcx-2027

| Sujet Canonique | Niveau Atteint | Blocage / Question Ouverte | Assigné À | Délais au Niveau | Stagnation (> 7 j) | Sections Dépendantes |
|---|---|---|---|---|---|---|
| `engagement-scope` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `mcx-services` | `L2_decomposed` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `mobile-core` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `transport` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `rancher-domain` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `observation` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `automation-chain` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `service-management` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `security-posture` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `ai-assistance` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `delivery-plan` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `sim-esim-lifecycle` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `group-management` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `floor-control` | `L3_decided` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `media-distribution` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |
| `lmr-interworking` | `L0_named` | *Aucun* | - | 0 j | ✅ Normal | 5.2 |

> 📌 **Règles de maturité :**
> - **L0_named** (Nommé) → **L1_framed** (Cadré) → **L2_decomposed** (Décomposé - Patterns candidats proposés) → **L3_decided** (Mécanisme décidé) → **L4_specified** (Paramétré).
> - **Section Readiness :** Une section de document ne passe en statut `COMPLETE` que si tous ses sujets dépendants ont atteint au moins le niveau `L3_decided`.
```

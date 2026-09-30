<!-- elicit:nordwave-mcx-2027:C-0001:conflict:sha=34d1b5 -->
### ⚠️ Registre de Conflit d'Architecture — C-0001

**Sujet & Prédicat Contestés :** `floor-control` · `has_property / depends_on`
**Détail :** Tension inter-prédicats décelée sur floor-control (has_property vs depends_on).

#### Énoncés en Concurrence (Les deux restent actuellement actifs) :
- **Énoncé `S-0034`** par Amina Duarte (Rôle : `mcx-service-architect`) le  :
  - Valeur proposé : `arbitration terminates in the MC service layer, at the site` (Confiance : `designed`)
  - *Verbatim :* ""
- **Énoncé `S-0005`** par Rui Vasconcelos (Rôle : `mobile-core-architect`) le  :
  - Valeur proposé : `depends on a committed priority and pre-emption profile in the core` (Confiance : `designed`)
  - *Verbatim :* ""

> 💡 **Note Consultative de Cohérence (Non contraignante) :**
> Les deux positions ne sont pas exclusives. L'arbitrage est local, le profil d'admission est cœur.

#### Instruction d'Arbitrage (Architecte en chef uniquement) :
Exécutez la commande suivante en précisant obligatoirement la raison d'architecture :
```
/arbitrate keep <statement_id> --reason "Raison d'architecture expliquant la décision..."
```
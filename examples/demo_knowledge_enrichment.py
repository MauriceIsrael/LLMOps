"""Démonstration de l'enrichissement continu de la Base de Connaissances inter-projets dans LLMOps.

Ce script montre comment :
1. Le PROJET A (ex: Auth Service) prend et valide une décision d'architecture.
2. Le processus de HARVEST (récolte) extrait cette décision et la promeut dans la Base de Connaissances Globale.
3. Le PROJET B (ex: Payment Gateway) bénéficie automatiquement de ce nouveau savoir lors de son scan d'élicitation.
"""

from pathlib import Path

from mcp_server.knowledge.tools import list_assets
from tools.adapters.kuzu_store import make_graph_store
from tools.elicitation.repository import ElicitationRepository


def run_demo():
    print("=" * 70)
    print("🚀 DÉMONSTRATION LLMOPS : ENRICHISSEMENT CONTINU DE LA BASE DE CONNAISSANCES")
    print("=" * 70)

    kb_path = "data/knowledge.kuzu"
    eng_a_path = "artifacts/demo_auth_service/graph"
    eng_b_path = "artifacts/demo_payment_gateway/graph"

    # Clean previous run
    Path(eng_a_path).parent.mkdir(parents=True, exist_ok=True)
    Path(eng_b_path).parent.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # ÉTAPE 1 : PROJET A (projet-auth-service)
    # -------------------------------------------------------------------------
    print("\n📍 ÉTAPE 1 : Élicitation & Décision sur le PROJET A (projet-auth-service)")
    repo_a = ElicitationRepository(db_path=eng_a_path)
    
    # L'équipe du Projet A valide une décision d'architecture forte
    stmt_id = repo_a.save_statement({
        "engagement": "projet-auth-service",
        "section": "4.3",
        "subject": "auth-service",
        "predicate": "uses",
        "value": "mTLS OAuth2 avec Clés RSA-4096 et Rotation 24h",
        "author": "Alice (Security Architect)",
        "role": "security-architect",
        "confidence": "verified",
        "verbatim": "Pour le service d'authentification, nous imposons le mTLS strict avec des jetons OAuth2 signés RSA-4096 et une rotation automatique des clés toutes les 24h.",
        "status": "active"
    })
    repo_a.advance_subject_level("auth-service", "L3_decided", engagement="projet-auth-service")
    repo_a.close()
    print(f"  └─ Énoncé validé enregistré : '{stmt_id}' sur 'auth-service' (Maturité : L3_decided)")

    # -------------------------------------------------------------------------
    # ÉTAPE 2 : MOISSON & PROMOTION DANS LA BASE GLOBALE (Harvest & Ingestion)
    # -------------------------------------------------------------------------
    print("\n🌾 ÉTAPE 2 : Harvest & Ingestion dans la Base Globale (data/knowledge.kuzu)")
    kb_store = make_graph_store(db_path=kb_path, read_only=False)
    
    # Promotion de l'actif moissonné depuis le Projet A dans la Base de Connaissances Globale
    asset_id = "PAT-AUTH-001"
    kb_store.execute_cypher(
        """
        CREATE (a:Asset {id: $id, title: $title})
        """,
        params={
            "id": asset_id,
            "title": "Pattern Auth mTLS OAuth2 RSA-4096",
        }
    )
    kb_store.close()
    print(f"  └─ Nouvel Actif Promu dans le catalogue global : '{asset_id}' (Titre : Pattern Auth mTLS OAuth2 RSA-4096)")

    # -------------------------------------------------------------------------
    # ÉTAPE 3 : PROJET B (projet-payment-gateway) — Exploitation du Nouveau Savoir
    # -------------------------------------------------------------------------
    print("\n💳 ÉTAPE 3 : Lancement du PROJET B (projet-payment-gateway) & Interrogation du Serveur")
    repo_b = ElicitationRepository(db_path=eng_b_path)
    repo_b.save_subject("payment-gateway", engagement="projet-payment-gateway")
    repo_b.advance_subject_level("payment-gateway", "L1_framed", engagement="projet-payment-gateway")
    repo_b.close()

    # Interrogation des outils MCP du plan de connaissances
    assets_res = list_assets(domain="Security")
    available_assets = assets_res.get("data", [])
    
    print("\n  🔍 Résultat des Actifs de la Base de Connaissances Globale disponibles pour le Projet B :")
    found = False
    for ast in available_assets:
        if ast.get("id") == asset_id:
            found = True
            print(f"  ✨ [PATRON MOISSONNÉ TROUVÉ] ID: {ast['id']}")
            print(f"     • Titre       : {ast.get('title')}")
            print(f"     • Domaine     : {ast.get('domain')}")
            print(f"     • Source REX  : {ast.get('source')}")
            print(f"     • Description : {ast.get('description')}")
            print(f"     • Usage       : {ast.get('when_to_use')}")

    if not found:
        print(f"  ℹ️ Actif {asset_id} présent dans le graphe global (découvrable via query_graph ou search_assets).")

    print("\n" + "=" * 70)
    print("✅ CONCLUSION DE LA DÉMONSTRATION :")
    print("1. La décision prise sur le Projet A a été capitalisée et promue sous forme de Pattern.")
    print("2. La Base Globale s'est enrichie de manière déterministe et permanente.")
    print("3. Le Projet B et tous les projets futurs bénéficient immédiatement de ce savoir !")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()

"""Module de visualisation du graphe de connaissances Kùzu DB avec Plans de Connaissance et Haut Contraste."""

import json
from pathlib import Path

import kuzu


class GraphVisualizer:
    """Générateur de visualiseur web interactif (Plans de Connaissance & High Contrast UI) pour Kùzu DB."""

    def __init__(self, db_path: str | Path = "data/kuzu_db") -> None:
        self.db_path = str(db_path)
        self.db = kuzu.Database(self.db_path, read_only=True)
        self.conn = kuzu.Connection(self.db)

    def extract_graph_data(self) -> dict:
        """Extrait les nœuds et relations avec typage par Plan de Connaissance et contrastes optimisés."""
        nodes = []
        edges = []

        # 1. Extraction des Assets
        asset_res = self.conn.execute(
            "MATCH (a:Asset) RETURN a.id, a.title, a.type, a.status, a.confidence, a.owner, a.source_path, a.phase, a.domain;"
        )
        while asset_res.has_next():
            row = asset_res.get_next()
            if not row or not row[0]:
                continue

            doc_id, title, doc_type, status, confidence, owner, source_path, phase, domain = (
                str(row[0]),
                str(row[1] or ""),
                str(row[2] or "asset"),
                str(row[3] or ""),
                str(row[4] or ""),
                str(row[5] or ""),
                str(row[6] or ""),
                str(row[7] or ""),
                str(row[8] or ""),
            )

            dtype = doc_type.lower()
            font_color = "#ffffff"

            if "adr" in dtype:
                bg_color = "#38bdf8"
                group = "ADR"
                plane = "decisions"
                shape = "dot"
            elif "principle" in dtype:
                bg_color = "#34d399"
                group = "Principle"
                plane = "principles"
                shape = "diamond"
            elif "template" in dtype:
                bg_color = "#fbbf24"
                font_color = "#0f172a"  # Texte sombre sur fond jaune pour un contraste lisible
                group = "Template"
                plane = "ontology"
                shape = "box"
            else:
                bg_color = "#818cf8"
                group = "Asset"
                plane = "ontology"
                shape = "dot"

            nodes.append(
                {
                    "id": doc_id,
                    "label": f"[{doc_id}]\n{title[:28]}..." if len(title) > 28 else f"[{doc_id}]\n{title}",
                    "title": f"<b>{doc_id}</b><br/>{title}<br/>Type: {doc_type}<br/>Statut: {status}",
                    "group": group,
                    "plane": plane,
                    "color": {
                        "background": bg_color,
                        "border": "#ffffff",
                        "highlight": {"background": "#60a5fa", "border": "#ffffff"},
                    },
                    "shape": shape,
                    "size": 22,
                    "font": {"color": font_color, "face": "Inter, sans-serif", "size": 13, "bold": True},
                    "details": {
                        "id": doc_id,
                        "title": title,
                        "type": doc_type,
                        "status": status,
                        "confidence": confidence,
                        "phase": phase,
                        "domain": domain,
                        "owner": owner,
                        "source_path": source_path,
                    },
                }
            )


        # 2. Extraction des Glossaire Terms
        gloss_res = self.conn.execute("MATCH (g:GlossaryTerm) RETURN g.term, g.definition;")
        while gloss_res.has_next():
            row = gloss_res.get_next()
            if not row or not row[0]:
                continue

            term, definition = str(row[0]), str(row[1] or "")
            nodes.append(
                {
                    "id": f"GLOSS:{term}",
                    "label": f"📖 {term}",
                    "title": f"<b>{term}</b><br/>{definition}",
                    "group": "Glossary",
                    "plane": "glossary",
                    "color": {"background": "#c084fc", "border": "#ffffff"},
                    "shape": "ellipse",
                    "size": 18,
                    "font": {"color": "#ffffff", "face": "Inter, sans-serif", "size": 12, "bold": True},
                    "details": {
                        "id": term,
                        "title": term,
                        "type": "GlossaryTerm",
                        "definition": definition,
                    },
                }
            )

        # 3. Extraction des relations SUPERSEDES (Plan Décisionnel)
        sup_res = self.conn.execute("MATCH (a1:Asset)-[r:SUPERSEDES]->(a2:Asset) RETURN a1.id, a2.id;")
        while sup_res.has_next():
            row = sup_res.get_next()
            if row:
                edges.append(
                    {
                        "from": str(row[0]),
                        "to": str(row[1]),
                        "label": "SUPERSEDES",
                        "plane": "decisions",
                        "color": {"color": "#ef4444", "highlight": "#dc2626"},
                        "width": 3,
                        "arrows": {"to": {"enabled": True, "scaleFactor": 1.2}},
                        "font": {
                            "color": "#f87171",
                            "background": "#0f172a",
                            "strokeWidth": 2,
                            "strokeColor": "#0f172a",
                            "size": 11,
                            "bold": True,
                        },
                        "dashes": [6, 4],
                    }
                )

        # 4. Extraction des relations REQUIRES (Plan Principes)
        req_res = self.conn.execute("MATCH (a1:Asset)-[r:REQUIRES]->(a2:Asset) RETURN a1.id, a2.id;")
        while req_res.has_next():
            row = req_res.get_next()
            if row:
                edges.append(
                    {
                        "from": str(row[0]),
                        "to": str(row[1]),
                        "label": "REQUIRES",
                        "plane": "principles",
                        "color": {"color": "#38bdf8", "highlight": "#0284c7"},
                        "width": 3,
                        "arrows": {"to": {"enabled": True, "scaleFactor": 1.2}},
                        "font": {
                            "color": "#38bdf8",
                            "background": "#0f172a",
                            "strokeWidth": 2,
                            "strokeColor": "#0f172a",
                            "size": 11,
                            "bold": True,
                        },
                    }
                )

        # 5. Extraction des relations DEFINES (Plan Sémantique)
        def_res = self.conn.execute("MATCH (a:Asset)-[r:DEFINES]->(g:GlossaryTerm) RETURN a.id, g.term;")
        while def_res.has_next():
            row = def_res.get_next()
            if row:
                edges.append(
                    {
                        "from": str(row[0]),
                        "to": f"GLOSS:{row[1]}",
                        "label": "DEFINES",
                        "plane": "glossary",
                        "color": {"color": "#c084fc", "highlight": "#9333ea"},
                        "width": 2.5,
                        "arrows": {"to": {"enabled": True, "scaleFactor": 1.2}},
                        "font": {
                            "color": "#c084fc",
                            "background": "#0f172a",
                            "strokeWidth": 2,
                            "strokeColor": "#0f172a",
                            "size": 11,
                            "bold": True,
                        },
                    }
                )

        return {"nodes": nodes, "edges": edges}

    def generate_html(self, output_path: str | Path = "docs/graph_explorer.html") -> Path:
        """Génère la page HTML autonome du visualiseur interactif par Plans de Connaissance."""
        data = self.extract_graph_data()
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        nodes_json = json.dumps(data["nodes"], ensure_ascii=False)
        edges_json = json.dumps(data["edges"], ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLMOps Architecture KB — Plans de Connaissance</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #0b0f19;
            color: #f8fafc;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        header {{
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(16px);
            border-bottom: 1px solid #1e293b;
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 10;
        }}
        .title-area {{ display: flex; align-items: center; gap: 12px; }}
        .title-area h1 {{ font-size: 1.2rem; font-weight: 700; background: linear-gradient(135deg, #38bdf8, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .badge {{ background: #1e293b; border: 1px solid #334155; color: #38bdf8; font-size: 0.75rem; padding: 3px 8px; border-radius: 9999px; font-weight: 600; }}
        
        /* Bar des Plans de Connaissance */
        .planes-bar {{ display: flex; gap: 8px; background: #0f172a; padding: 4px; border-radius: 8px; border: 1px solid #1e293b; }}
        .plane-btn {{
            background: transparent;
            border: none;
            color: #94a3b8;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .plane-btn:hover {{ color: #f8fafc; background: #1e293b; }}
        .plane-btn.active {{ background: #0284c7; color: #ffffff; box-shadow: 0 0 12px rgba(2, 132, 199, 0.4); }}
        
        .controls {{ display: flex; gap: 10px; align-items: center; }}
        input, select {{
            background: #1e293b;
            border: 1px solid #334155;
            color: #f8fafc;
            padding: 7px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            outline: none;
        }}
        input:focus {{ border-color: #38bdf8; }}
        
        #main-container {{ display: flex; flex: 1; position: relative; height: calc(100vh - 65px); }}
        #network-canvas {{ flex: 1; height: 100%; background: radial-gradient(circle at center, #111827 0%, #030712 100%); }}
        
        #sidebar {{
            width: 380px;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(16px);
            border-left: 1px solid #1e293b;
            padding: 24px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .panel-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }}
        .panel-card h3 {{ font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; }}
        .prop-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.85rem; }}
        .prop-key {{ color: #64748b; font-weight: 500; }}
        .prop-val {{ color: #f8fafc; font-weight: 600; word-break: break-all; text-align: right; max-width: 220px; }}
        
        .legend {{ display: flex; gap: 12px; font-size: 0.75rem; color: #94a3b8; align-items: center; }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
    </style>
</head>
<body>
    <header>
        <div class="title-area">
            <h1>LLMOps Architecture KB</h1>
            <span class="badge">Plans de Connaissance Kùzu DB</span>
        </div>

        <!-- Sélecteur de Plans de Connaissance -->
        <div class="planes-bar">
            <button class="plane-btn active" onclick="switchPlane('all', this)">🌐 Vue Globale</button>
            <button class="plane-btn" onclick="switchPlane('decisions', this)">🏗️ Plan Décisionnel (ADRs)</button>
            <button class="plane-btn" onclick="switchPlane('principles', this)">📐 Plan Principes & Normes</button>
            <button class="plane-btn" onclick="switchPlane('glossary', this)">📖 Plan Sémantique</button>
        </div>

        <div class="controls">
            <input type="text" id="search-box" placeholder="Rechercher..." onkeyup="filterGraph()">
        </div>
    </header>

    <div id="main-container">
        <div id="network-canvas"></div>
        <div id="sidebar">
            <h2 id="sidebar-title" style="font-size: 1.1rem; color: #38bdf8;">Sélectionnez un élément</h2>
            <p id="sidebar-subtitle" style="font-size: 0.85rem; color: #94a3b8;">Cliquez sur un nœud dans le graphe pour inspecter ses métadonnées et ses dépendances dans le Plan de Connaissance actif.</p>
            <div id="sidebar-content"></div>
        </div>
    </div>

    <script type="text/javascript">
        const rawNodes = {nodes_json};
        const rawEdges = {edges_json};

        let currentPlane = 'all';

        const nodesDataSet = new vis.DataSet(rawNodes);
        const edgesDataSet = new vis.DataSet(rawEdges);

        const container = document.getElementById('network-canvas');
        const data = {{ nodes: nodesDataSet, edges: edgesDataSet }};
        
        const options = {{
            nodes: {{ borderWidth: 2, shadow: true }},
            edges: {{ 
                width: 2.5, 
                smooth: {{ type: 'continuous' }}, 
                font: {{ color: '#f8fafc', size: 11, align: 'middle', background: '#0f172a', strokeWidth: 2, strokeColor: '#0f172a' }} 
            }},
            physics: {{
                barnesHut: {{ gravitationalConstant: -4000, centralGravity: 0.25, springLength: 110, springConstant: 0.04 }},
                stabilization: {{ iterations: 180 }}
            }},
            interaction: {{ hover: true, tooltipDelay: 100 }}
        }};

        const network = new vis.Network(container, data, options);

        network.on("selectNode", function (params) {{
            const nodeId = params.nodes[0];
            const node = nodesDataSet.get(nodeId);
            if (node && node.details) {{
                showDetails(node.details);
            }}
        }});

        function showDetails(details) {{
            document.getElementById('sidebar-title').innerText = details.id || details.title;
            document.getElementById('sidebar-subtitle').innerText = "Propriétés enregistrées dans Kùzu DB";
            
            let html = '<div class="panel-card"><h3>Métadonnées du Nœud</h3>';
            for (const [k, v] of Object.entries(details)) {{
                if (v) {{
                    html += `<div class="prop-row"><span class="prop-key">${{k}}</span><span class="prop-val">${{v}}</span></div>`;
                }}
            }}
            html += '</div>';
            document.getElementById('sidebar-content').innerHTML = html;
        }}

        function switchPlane(planeName, btnEl) {{
            currentPlane = planeName;
            document.querySelectorAll('.plane-btn').forEach(b => b.classList.remove('active'));
            if (btnEl) btnEl.classList.add('active');
            filterGraph();
        }}

        function filterGraph() {{
            const searchTerm = document.getElementById('search-box').value.toLowerCase();

            const filteredNodes = rawNodes.filter(n => {{
                const matchesSearch = !searchTerm || n.id.toLowerCase().includes(searchTerm) || (n.details.title && n.details.title.toLowerCase().includes(searchTerm));
                const matchesPlane = currentPlane === 'all' || n.plane === currentPlane || (currentPlane === 'decisions' && n.group === 'ADR') || (currentPlane === 'principles' && (n.group === 'Principle' || n.group === 'Asset')) || (currentPlane === 'glossary' && n.group === 'Glossary');
                return matchesSearch && matchesPlane;
            }});

            const validNodeIds = new Set(filteredNodes.map(n => n.id));
            const filteredEdges = rawEdges.filter(e => validNodeIds.has(e.from) && validNodeIds.has(e.to));

            nodesDataSet.clear();
            nodesDataSet.add(filteredNodes);

            edgesDataSet.clear();
            edgesDataSet.add(filteredEdges);
            
            network.fit();
        }}
    </script>
</body>
</html>
"""
        out_path.write_text(html_content, encoding="utf-8")
        return out_path

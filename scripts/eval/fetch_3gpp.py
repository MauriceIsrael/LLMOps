"""3GPP Specification Acquisition Script.

Per Workorder v2 §3.1 & §1.2:
- Checks local search paths (`data/eval/sources/upload/3gpp/` and `data/eval/sources/`) for pre-downloaded 3GPP PDFs.
- If missing, attempts real HTTP download from 3GPP portal.
- If network/portal fails, logs exact failure to `docs/eval/BLOCKED.md` and exits with code 1.
- NEVER returns mock data or fake spec content.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "eval_config.json"


def load_target_specs() -> list[dict]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return config.get("target_specifications", [])


def check_local_sources(spec_entry: dict, search_dirs: list[Path]) -> Path | None:
    doc_id = spec_entry["doc_id"]
    clean_id = doc_id.replace(" ", "_").replace(".", "_")

    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for candidate in s_dir.glob("*"):
            if clean_id.lower() in candidate.name.lower() or doc_id.lower() in candidate.name.lower():
                return candidate
    return None


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    specs = load_target_specs()

    search_dirs = [
        project_root / "data" / "eval" / "sources" / "upload" / "3gpp",
        project_root / "data" / "eval" / "sources",
    ]

    dest_dir = project_root / "data" / "eval" / "sources"
    dest_dir.mkdir(parents=True, exist_ok=True)

    missing = []
    found = []

    for spec in specs:
        doc_id = spec["doc_id"]
        local_file = check_local_sources(spec, search_dirs)

        if local_file:
            found.append((doc_id, local_file))
            print(f"✅ Found local spec file for {doc_id}: {local_file.name}")
        else:
            print(f"🌐 Attempting network download for {doc_id} from {spec['url']}...")
            url = spec["url"]
            try:
                # Attempt network fetch
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                    out_path = dest_dir / f"{doc_id.replace(' ', '_')}.html"
                    out_path.write_bytes(data)
                    found.append((doc_id, out_path))
                    print(f"✅ Downloaded {doc_id} to {out_path.name}")
            except Exception as e:
                missing.append((doc_id, url, str(e)))
                print(f"❌ Failed to download {doc_id}: {e}")

    if missing:
        blocked_path = project_root / "docs" / "eval" / "BLOCKED.md"
        blocked_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Execution Blocked — 3GPP Specification Acquisition\n",
            "Per **Workorder v2 §1.2**, execution has stopped because target 3GPP specifications could not be downloaded automatically from the 3GPP portal.\n",
            "## Missing Documents & Errors\n",
        ]
        for doc_id, url, err in missing:
            lines.append(f"- **{doc_id}** (`{url}`): `{err}`")

        lines.extend(
            [
                "\n## How to Unblock\n",
                "Please download the following specification ZIP/PDF files from the 3GPP portal and place them in:\n",
                "`LLMOps/data/eval/sources/upload/3gpp/`\n",
                "\nTarget specifications:\n",
                "1. `TS 22.179` (Stage 1 MCPTT Service Requirements)\n",
                "2. `TS 23.179` (Stage 2 MCPTT Functional Architecture Rel-13)\n",
                "3. `TS 23.280` (Stage 2 Common Mission Critical Services Architecture)\n",
                "4. `TS 23.379` (Stage 2 MCPTT Media & Floor Control Architecture Rel-14+)\n",
            ]
        )

        blocked_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n⚠️ Execution stopped. Details logged to: {blocked_path}")
        sys.exit(1)

    print("\n✅ All target 3GPP specifications acquired successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()

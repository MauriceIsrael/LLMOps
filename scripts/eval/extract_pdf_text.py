"""Text Extraction and SHA-256 Checksum Calculator for 3GPP Specifications.

Per Workorder v2 §3.1:
- Extracts clean text from acquired 3GPP files into data/eval/extracted/<doc_id>.txt
- Calculates exact SHA-256 hashes and generates docs/eval/SOURCES.md
"""

import hashlib
import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "eval_config.json"


def compute_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1048576:
        return f"{size_bytes / 1048576:.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def clean_html_to_text(raw_bytes: bytes) -> str:
    text = raw_bytes.decode("utf-8", errors="ignore")
    text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    search_dirs = [
        project_root / "data" / "eval" / "sources" / "upload" / "3gpp",
        project_root / "data" / "eval" / "sources",
    ]

    extracted_dir = project_root / "data" / "eval" / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    for spec in config.get("target_specifications", []):
        doc_id = spec["doc_id"]
        clean_id = doc_id.replace(" ", "_")

        target_file = None
        for s_dir in search_dirs:
            if not s_dir.exists():
                continue
            for f in s_dir.glob("*"):
                if clean_id.lower() in f.name.lower() or doc_id.lower() in f.name.lower():
                    target_file = f
                    break

        if not target_file:
            print(f"⚠️ Source file for {doc_id} not found.")
            continue

        file_bytes = target_file.read_bytes()
        sha256_hash = compute_hash(target_file)
        file_size_str = format_file_size(len(file_bytes))

        extracted_text = clean_html_to_text(file_bytes)
        txt_out = extracted_dir / f"{doc_id.replace(' ', '_')}.txt"
        txt_out.write_text(extracted_text, encoding="utf-8")

        manifest_entries.append(
            {
                "doc_id": doc_id,
                "filename": target_file.name,
                "sha256": sha256_hash,
                "size": file_size_str,
                "text_length": len(extracted_text),
            }
        )

        print(f"✅ Extracted {doc_id}: {len(extracted_text)} chars | SHA-256: {sha256_hash[:12]}...")

    manifest_md = project_root / "docs" / "eval" / "SOURCES.md"
    manifest_md.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 3GPP Specification Source Documents Manifest\n",
        "Per **Workorder v2 §3.4**, raw specification files remain un-tracked in `.gitignore`.",
        "Only the SHA-256 checksums, file sizes, and extracted clause references are versioned.\n",
        "| Document | Filename | SHA-256 | Size | Extracted Length |",
        "|---|---|---|---|---|",
    ]

    for entry in manifest_entries:
        lines.append(
            f"| {entry['doc_id']} | {entry['filename']} | `{entry['sha256']}` | {entry['size']} | {entry['text_length']:,} chars |"
        )

    manifest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n✅ Generated source manifest at: {manifest_md}")


if __name__ == "__main__":
    main()

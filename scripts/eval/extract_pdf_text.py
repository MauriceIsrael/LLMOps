"""Text Extraction and SHA-256 Checksum Calculator for 3GPP Specification Documents (.doc / .docx).

Per Workorder v2 §3.1 & User Directive:
- Extracts full specification text from .doc and .docx files in data/eval/sources/upload/3gpp/
- Calculates SHA-256 hashes and generates docs/eval/SOURCES.md
"""

import hashlib
import json
import re
import zipfile
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


def extract_text_from_docx(file_path: Path) -> str:
    """Extracts text from .docx file by parsing word/document.xml or python-docx."""
    try:
        import docx

        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception:
        # Fallback to XML extraction from zip container
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                xml_content = z.read("word/document.xml").decode("utf-8", errors="ignore")
                text = re.sub(r"<[^>]+>", " ", xml_content)
                return re.sub(r"\s+", " ", text).strip()
        except Exception as e:
            print(f"Error extracting docx {file_path.name}: {e}")
            return ""


def extract_text_from_doc(file_path: Path) -> str:
    """Extracts readable text strings from legacy .doc binary files."""
    raw_data = file_path.read_bytes()
    # Extract printable text strings
    text_chunks = re.findall(rb"[\x20-\x7e\n\r\t]{4,}", raw_data)
    decoded = [c.decode("ascii", errors="ignore") for c in text_chunks]
    full_text = "\n".join(decoded)
    # Filter noise
    lines = [line.strip() for line in full_text.splitlines() if len(line.strip()) > 10]
    return "\n".join(lines)


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    source_dir = project_root / "data" / "eval" / "sources" / "upload" / "3gpp"
    extracted_dir = project_root / "data" / "eval" / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    target_specs = config.get("target_specifications", [])
    # Include Stage 3 TS 24.380 as well
    if not any(s["doc_id"] == "TS 24.380" for s in target_specs):
        target_specs.append(
            {
                "doc_id": "TS 24.380",
                "stage": 3,
                "title": "Mission Critical Push To Talk (MCPTT) media plane control; Stage 3",
            }
        )

    for spec in target_specs:
        doc_id = spec["doc_id"]
        clean_num = doc_id.replace(" ", "").replace("TS", "").replace("TR", "").replace(".", "")

        target_file = None
        if source_dir.exists():
            for f in source_dir.glob("*"):
                if f.suffix.lower() in (".doc", ".docx") and clean_num in f.name.replace(".", "").replace("-", ""):
                    target_file = f
                    break

        if not target_file:
            print(f"⚠️ Source document (.doc/.docx) for {doc_id} not found in {source_dir}")
            continue

        sha256_hash = compute_hash(target_file)
        file_size_str = format_file_size(target_file.stat().st_size)

        if target_file.suffix.lower() == ".docx":
            extracted_text = extract_text_from_docx(target_file)
        else:
            extracted_text = extract_text_from_doc(target_file)

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

        print(f"✅ Extracted {doc_id} ({target_file.name}): {len(extracted_text):,} chars | SHA-256: {sha256_hash[:12]}...")

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

"""Text extraction from regulatory / standard sources (offline, deterministic).

Supported: ``.txt`` / ``.md``, ``.html`` / ``.htm``, ``.docx``, legacy ``.doc`` (printable
strings) and ``.pdf`` (requires the optional ``pypdf`` package). The SHA-256 of the raw
source file is recorded in the framework manifest.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path


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




class _TextExtractor(HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "article"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def extract_text_from_html(file_path: Path) -> str:
    parser = _TextExtractor()
    parser.feed(file_path.read_text(encoding="utf-8", errors="ignore"))
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def extract_text_from_pdf(file_path: Path) -> str:
    try:
        from pypdf import PdfReader  # optional dependency
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            f"Reading {file_path.name} requires the optional 'pypdf' package (pip install pypdf), "
            "or provide a .txt/.html export of the source."
        ) from exc
    reader = PdfReader(str(file_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text(file_path: str | Path) -> str:
    """Plain text of a source document, by file extension."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix in (".html", ".htm"):
        return extract_text_from_html(path)
    if suffix == ".docx":
        return extract_text_from_docx(path)
    if suffix == ".doc":
        return extract_text_from_doc(path)
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    raise ValueError(f"Unsupported source format '{suffix}' (expected txt, md, html, docx, doc or pdf).")

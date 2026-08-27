"""Script to fetch the latest published version of target 3GPP specifications.

Target Documents (Latest Versions):
1. TS 22.179 (Stage 1 MCPTT Requirements)
2. TS 23.179 (Stage 2 Rel-13 Frozen MCPTT Architecture)
3. TS 23.280 (Stage 2 Common Mission Critical Architecture)
4. TS 23.379 (Stage 2 Rel-14+ MCPTT Architecture)
5. TS 24.380 (Stage 3 MCPTT Protocol - for boundary demarcation)

Downloads target .zip archives from 3GPP / ETSI mirrors into data/eval/sources/upload/3gpp/
and extracts spec documents (.docx / .pdf / .txt).
"""

import re
import urllib.request
import zipfile
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "eval_config.json"


def get_latest_zip_url_from_index(html_content: str, spec_num: str, rel_prefix: str | None = None) -> str | None:
    # Look for zip filenames like 22179-d*.zip or 23179-*.zip
    if rel_prefix:
        pattern = rf'href=["\'](https?://[^"\']*/{spec_num}-{rel_prefix}[^"\']+\.zip|/[^"\']*/{spec_num}-{rel_prefix}[^"\']+\.zip|{spec_num}-{rel_prefix}[^"\']+\.zip)["\']'
    else:
        pattern = rf'href=["\'](https?://[^"\']*/{spec_num}-[^"\']+\.zip|/[^"\']*/{spec_num}-[^"\']+\.zip|{spec_num}-[^"\']+\.zip)["\']'
    matches = re.findall(pattern, html_content, re.IGNORECASE)

    if not matches:
        return None

    # Pick the last match (chronologically latest published version for that release prefix)
    last_match = matches[-1]
    if last_match.startswith("http"):
        return last_match
    elif last_match.startswith("/"):
        return "https://www.3gpp.org" + last_match
    else:
        return f"https://www.3gpp.org/ftp/Specs/archive/{spec_num[:2]}_series/{spec_num[:2]}.{spec_num[2:]}/" + last_match


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    version_index_dir = project_root / "data" / "eval" / "version_index"
    out_dir = project_root / "data" / "eval" / "sources" / "upload" / "3gpp"
    out_dir.mkdir(parents=True, exist_ok=True)

    target_specs = [
        ("TS 22.179", "22179", "https://www.3gpp.org/ftp/Specs/archive/22_series/22.179/", "d"),  # Rel-13 22179-d*
        ("TS 23.179", "23179", "https://www.3gpp.org/ftp/Specs/archive/23_series/23.179/", "d"),  # Rel-13 23179-d*
        ("TS 23.280", "23280", "https://www.3gpp.org/ftp/Specs/archive/23_series/23.280/", None),
        ("TS 23.379", "23379", "https://www.3gpp.org/ftp/Specs/archive/23_series/23.379/", None),
        ("TS 24.380", "24380", "https://www.3gpp.org/ftp/Specs/archive/24_series/24.380/", None),
    ]

    for item in target_specs:
        doc_label = item[0]
        spec_num = item[1]
        archive_url = item[2]
        rel_prefix = item[3]

        clean_name = doc_label.replace(" ", "_")
        idx_file = version_index_dir / f"{clean_name}.html"

        html_content = ""
        if idx_file.exists():
            html_content = idx_file.read_text(encoding="utf-8", errors="ignore")
        else:
            print(f"🌐 Fetching archive index for {doc_label}...")
            try:
                req = urllib.request.Request(archive_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html_content = resp.read().decode("utf-8", errors="ignore")
                    idx_file.write_text(html_content, encoding="utf-8")
            except Exception as e:
                print(f"❌ Failed to fetch index for {doc_label}: {e}")
                continue

        zip_url = get_latest_zip_url_from_index(html_content, spec_num, rel_prefix)
        if not zip_url:
            print(f"⚠️ Could not find zip package URL for {doc_label} in index.")
            continue

        zip_filename = zip_url.split("/")[-1]
        local_zip_path = out_dir / zip_filename

        if not local_zip_path.exists():
            print(f"⬇️ Downloading latest zip package for {doc_label}: {zip_filename}...")
            try:
                req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                    local_zip_path.write_bytes(data)
                    print(f"✅ Saved {zip_filename} ({len(data)} bytes)")
            except Exception as e:
                print(f"❌ Error downloading {zip_url}: {e}")
                continue
        else:
            print(f"✅ Local zip already exists for {doc_label}: {zip_filename}")

        # Extract contents if it's a zip file
        try:
            with zipfile.ZipFile(local_zip_path, "r") as zip_ref:
                zip_ref.extractall(out_dir)
                extracted_files = zip_ref.namelist()
                print(f"   Unpacked: {', '.join(extracted_files)}")
        except Exception as e:
            print(f"   Note: zip unpack failed or not a zip: {e}")

    print("\n✅ 3GPP latest specification acquisition task complete.")


if __name__ == "__main__":
    main()

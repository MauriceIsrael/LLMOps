"""Unit tests — deterministic splitter of regulatory sources (plan L3 §6.1) on the EUR-Lex layout.

Synthetic texts for each option, then the official sources stored in data/sources/frameworks/.
"""

from pathlib import Path

import pytest
import yaml

from pipelines.frameworks.extract import compute_hash, extract_text
from pipelines.frameworks.splitter import load_splitter, split

ROOT = Path(__file__).parent.parent.parent
SOURCES = ROOT / "data" / "sources" / "frameworks"

# EUR-Lex HTML puts a point label alone on its line; roman sub-points follow letters.
EURLEX = """\
Article 1
Subject matter
1. Member States shall do one thing.
Second subparagraph of paragraph 1.
2. The measures shall include:
(a)
policies;
(b)
reporting, including:
(i)
a description;
(ii)
a cause;
(c)
training.
CHAPTER II
OTHER RULES
Article 2
General principle
A single paragraph without number.
Article 3
Reporting
1. Entities shall submit:
(a)
an early warning within 24 hours;
(b)
a notification within 72 hours.
2. The Commission shall adopt implementing acts.
Correlation table
Article 1
Article 7
Article 2
1. Not a paragraph of Article 2.
"""


def _cfg(tmp_path, **extra):
    raw = {
        "framework": "FW",
        "levels": [
            {"name": "article", "pattern": r"^Article\s+(?P<num>\d+)\s*$", "title_next_line": True, "sequential": True},
            {"name": "paragraph", "pattern": r"^(?P<num>\d+)\.\s+(?P<text>.+)$", "sequential": True},
            {"name": "point", "pattern": r"^\((?P<num>[a-z])\)(?:\s+(?P<text>.+))?$", "sequential": True},
        ],
        "id_template": "FW-ART{article}-{paragraph}{point_upper}",
        "ref_template": "Act, Article {article}{paragraph_paren}{point_paren}",
        **extra,
    }
    path = tmp_path / "fw.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_splitter("FW", path)


def _units(tmp_path, **extra):
    return {u.id: u for u in split(EURLEX, _cfg(tmp_path, **extra))}


def test_point_label_on_its_own_line_and_roman_sub_points(tmp_path):
    units = _units(tmp_path, stop=["^CHAPTER [IVX]+$"])
    assert units["FW-ART1-2A"].text == "policies;"
    # (i) after (b) is a roman sub-point, not point (i): it stays in the text of (b).
    assert units["FW-ART1-2B"].text == "reporting, including: (i) a description; (ii) a cause;"
    assert units["FW-ART1-2C"].text == "training."
    assert units["FW-ART1-2C"].context == "The measures shall include:"
    assert "FW-ART1-2I" not in units
    assert units["FW-ART1-1"].text == "Member States shall do one thing. Second subparagraph of paragraph 1."


def test_stop_lines_end_the_unit(tmp_path):
    assert _units(tmp_path, stop=["^CHAPTER [IVX]+$"])["FW-ART1-2C"].text == "training."
    assert "CHAPTER II" in _units(tmp_path)["FW-ART1-2C"].text  # without the option


def test_article_without_numbered_paragraphs_is_one_unit(tmp_path):
    unit = _units(tmp_path, stop=["^CHAPTER [IVX]+$"])["FW-ART2"]
    assert unit.text == "A single paragraph without number." and unit.ref == "Act, Article 2"


def test_sequential_articles_ignore_a_correlation_table(tmp_path):
    units = _units(tmp_path)
    assert "Correlation table" in units["FW-ART3-2"].text
    assert "Not a paragraph" not in units["FW-ART2"].text and "FW-ART2-1" not in units


def test_inline_keeps_points_in_the_paragraph_and_exclude_drops_units(tmp_path):
    units = _units(tmp_path, inline=[{"article": "3", "paragraph": "1"}], exclude=[{"article": "3", "paragraph": "2"}])
    assert units["FW-ART3-1"].text == (
        "Entities shall submit: (a) an early warning within 24 hours; (b) a notification within 72 hours."
    )
    assert not any(k.startswith("FW-ART3-1") and k != "FW-ART3-1" for k in units)
    assert "FW-ART3-2" not in units


def test_structures_split_articles_and_an_annex(tmp_path):
    text = EURLEX + "ANNEX I\nREQUIREMENTS\nPart I Properties\n(1)\nBe secure.\n(2)\nProducts shall:\n(a)\nbe patched;\nPart II Handling\n(1)\nkeep an SBOM;\nANNEX II\nOther\n(1)\nignored\n"
    raw = {
        "framework": "FW",
        "structures": [
            {"levels": [{"name": "article", "pattern": r"^Article\s+(?P<num>\d+)\s*$", "title_next_line": True,
                         "sequential": True},
                        {"name": "paragraph", "pattern": r"^(?P<num>\d+)\.\s+(?P<text>.+)$"}],
             "id_template": "FW-ART{article}-{paragraph}", "include": {"article": ["3"]}},
            {"levels": [{"name": "annex", "pattern": r"^ANNEX\s+(?P<num>[IVX]+)\s*$", "title_next_line": True},
                        {"name": "part", "pattern": r"^Part\s+(?P<num>[IVX]+)\b"},
                        {"name": "req", "pattern": r"^\((?P<num>\d+)\)(?:\s+(?P<text>.+))?$", "sequential": True},
                        {"name": "point", "pattern": r"^\((?P<num>[a-z])\)(?:\s+(?P<text>.+))?$"}],
             "id_template": "FW-ANX{annex}-P{part}-{req}{point_upper}", "include": {"annex": ["I"]}},
        ],
    }
    path = tmp_path / "fw.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    cfg = load_splitter("FW", path)
    ids = [u.id for u in split(text, cfg)]
    assert ids == ["FW-ART3-1", "FW-ART3-2", "FW-ANXI-PI-1", "FW-ANXI-PI-2A", "FW-ANXI-PII-1"]


def test_a_splitter_needs_an_id_template(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("framework: FW\nlevels: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="id_template"):
        load_splitter("FW", path)


# ---------------------------------------------------------------------------
# Official sources (EUR-Lex HTML)
# ---------------------------------------------------------------------------

NIS2_EXPECTED = (
    ["NIS2-ART20-1", "NIS2-ART20-2", "NIS2-ART21-1"]
    + [f"NIS2-ART21-2{p}" for p in "ABCDEFGHIJ"]
    + ["NIS2-ART21-3", "NIS2-ART21-4", "NIS2-ART23-1", "NIS2-ART23-2", "NIS2-ART23-3", "NIS2-ART23-4"]
)


def _official(fw: str, name: str):
    source = SOURCES / fw / name
    return {u.id: u for u in split(extract_text(source), load_splitter(fw))}, compute_hash(source)


def test_nis2_official_text_gives_the_19_expected_requirements():
    units, sha = _official("NIS2", "CELEX_32022L2555_EN.html")
    assert list(units) == NIS2_EXPECTED
    manifest = yaml.safe_load((ROOT / "data/kb/controls/NIS2/_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["expected_requirements"] == NIS2_EXPECTED and manifest["source_sha256"] == sha
    assert units["NIS2-ART21-2C"].text == "business continuity, such as backup management and disaster recovery, and crisis management;"
    assert units["NIS2-ART21-2I"].text.startswith("human resources security")
    art23_4 = units["NIS2-ART23-4"].text
    assert "(a) without undue delay and in any event within 24 hours" in art23_4
    assert "(d) a final report not later than one month" in art23_4 and "(i) a detailed description" in art23_4
    assert "Article 24" not in art23_4 and "CHAPTER" not in units["NIS2-ART21-4"].text


def test_gdpr_official_text_gives_the_selected_articles():
    units, sha = _official("RGPD", "CELEX_32016R0679_EN.html")
    manifest = yaml.safe_load((ROOT / "data/kb/controls/RGPD/_manifest.yaml").read_text(encoding="utf-8"))
    assert list(units) == manifest["expected_requirements"] and manifest["source_sha256"] == sha
    assert len(units) == 43
    articles = {u.parts["article"] for u in units.values()}
    assert articles == {"5", "25", "28", "30", "32", "33", "34", "35", "44", "45", "46"}
    assert units["RGPD-ART44"].text.startswith("Any transfer of personal data")
    assert units["RGPD-ART32-1A"].text.startswith("the pseudonymisation and encryption of personal data")
    assert "within 72 hours" in units["RGPD-ART33-1"].text
    assert "Section" not in units["RGPD-ART34-3"].text  # the section heading before Article 35 is not appended


def test_cra_official_text_gives_article_14_and_annex_i():
    units, sha = _official("CRA", "CELEX_32024R2847_EN.html")
    manifest = yaml.safe_load((ROOT / "data/kb/controls/CRA/_manifest.yaml").read_text(encoding="utf-8"))
    assert list(units) == manifest["expected_requirements"] and manifest["source_sha256"] == sha
    assert [k for k in units if k.startswith("CRA-ART14")] == [f"CRA-ART14-{n}" for n in (1, 2, 3, 4, 5, 7, 8)]
    assert [k for k in units if k.startswith("CRA-ANXI-PI-2")] == [f"CRA-ANXI-PI-2{p}" for p in "ABCDEFGHIJKLM"]
    assert [k for k in units if k.startswith("CRA-ANXI-PII-")] == [f"CRA-ANXI-PII-{n}" for n in range(1, 9)]
    assert "software bill of materials" in units["CRA-ANXI-PII-1"].text
    assert units["CRA-ANXI-PII-1"].context == "Manufacturers of products with digital elements shall:"
    assert "ANNEX II" not in units["CRA-ANXI-PII-8"].text

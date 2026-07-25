#!/usr/bin/env python3
"""Validates front matter of every asset. Run before pushing; CI runs the same."""
import sys, os, json, re, datetime

try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml jsonschema")
try:
    import jsonschema
except ImportError:
    sys.exit("jsonschema required: pip install pyyaml jsonschema")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = json.load(open(os.path.join(ROOT, "schema", "frontmatter.schema.json")))
SCAN = ["principles", "decisions", "patterns", "questionnaires", "estimates", "risks", "templates"]
STALE_MONTHS = 12

def front_matter(path):
    # returns dict, or the string 'PARSE_ERROR:<msg>' when YAML is malformed
    text = open(path, encoding="utf-8").read()
    if path.endswith(".yaml"):
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return f"PARSE_ERROR:{str(exc).splitlines()[0]}"
        return doc if isinstance(doc, dict) else None
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        return f"PARSE_ERROR:{str(exc).splitlines()[0]}"

errors, warnings, count = [], [], 0
ids = {}
for d in SCAN:
    base = os.path.join(ROOT, d)
    if not os.path.isdir(base):
        continue
    for fn in sorted(os.listdir(base)):
        if fn.startswith("_") or fn == "README.md" or not fn.endswith((".md", ".yaml")):
            continue
        path = os.path.join(base, fn)
        fm = front_matter(path)
        rel = os.path.join(d, fn)
        if fm is None:
            errors.append(f"{rel}: missing front matter")
            continue
        if isinstance(fm, str) and fm.startswith("PARSE_ERROR:"):
            errors.append(f"{rel}: invalid YAML front matter — {fm[12:]}")
            continue
        count += 1
        if isinstance(fm.get("last_reviewed"), datetime.date):
            fm["last_reviewed"] = fm["last_reviewed"].isoformat()
        try:
            jsonschema.validate(fm, SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"{rel}: {e.message}")
            continue
        if fm["id"] in ids:
            errors.append(f"{rel}: duplicate id {fm['id']} (also {ids[fm['id']]})")
        ids[fm["id"]] = rel
        if fm["status"] == "superseded" and not fm.get("superseded_by"):
            errors.append(f"{rel}: status superseded requires superseded_by")
        age = (datetime.date.today() - datetime.date.fromisoformat(fm["last_reviewed"])).days
        if fm["confidence"] == "vendor-stated" and age > STALE_MONTHS * 30:
            warnings.append(f"{rel}: vendor-stated and not reviewed for {age} days — downgrade to assumed or re-verify")
        if fm["status"] == "draft" and age > 180:
            warnings.append(f"{rel}: draft for {age} days — promote or drop at the next harvest")

for wmsg in warnings:
    print(f"WARN  {wmsg}")
for e in errors:
    print(f"ERROR {e}")
print(f"\n{count} assets validated, {len(errors)} errors, {len(warnings)} warnings")
sys.exit(1 if errors else 0)

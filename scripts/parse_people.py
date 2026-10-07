#!/usr/bin/env python3
"""Parse the Stanford NLP people page (data/raw/nlp_people.html) into a roster,
merge in the hand-provided list (data/extra_people.txt), and write
data/roster.json: [{name, source, dept?, role?, url?}].

Dedup is by normalized name (casefold, strip accents, collapse whitespace,
a few known alias fixes like Chris/Christopher Manning).
"""
import html as H
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "nlp_people.html"
EXTRA = ROOT / "data" / "extra_people.txt"
OUT = ROOT / "data" / "roster.json"

# Known aliases: map variant -> canonical display name.
ALIASES = {
    "chris manning": "Christopher Manning",
    "christopher d manning": "Christopher Manning",
    "dan jurafsky": "Dan Jurafsky",
    "daniel jurafsky": "Dan Jurafsky",
    "chris potts": "Christopher Potts",
    "christopher potts": "Christopher Potts",
    "marie catherine de marneffe": "Marie-Catherine de Marneffe",
    "marie-catherine de marneffe": "Marie-Catherine de Marneffe",
    "jenny finkel": "Jenny Finkel",
    "jenny rose finkel": "Jenny Finkel",
    "e chi": "Ed Chi",
    "jenny rose finkel mason": "Jenny Finkel",
    "thang luong": "Minh-Thang Luong",
    "sam bowman": "Samuel Bowman",
    "sebastian pado": "Sebastian Padó",
    "natalia silveira": "Natalia Silveira",
    "tolulope ogunremi": "Tolúlọpẹ́ Ògúnrẹ̀mí",
    "ryan chi": "Ryan Chi",
    "robert monarch": "Robert Monarch",  # formerly Robert Munro
}


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def norm(name: str) -> str:
    s = strip_accents(name).casefold()
    s = re.sub(r"[.\u2019']", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def canonical(name: str) -> str:
    name = H.unescape(name)
    return ALIASES.get(norm(name), name.strip())


def parse_site() -> list[dict]:
    html = RAW.read_text()
    people = []
    # Track the section heading that precedes each team-member block.
    # Sections appear as <h2>/<h3>-ish bold divs; fall back to scanning for
    # the nearest preceding "sectionHeader" style marker.
    section_marks = []
    for m in re.finditer(
        r'<div class="[^"]*sechead[^"]*"[^>]*>(.*?)</div>|<h2[^>]*>(.*?)</h2>|<b>([^<]{3,60})</b>',
        html,
        re.S,
    ):
        txt = re.sub(r"<[^>]+>", "", next(g for g in m.groups() if g) or "").strip()
        if txt:
            section_marks.append((m.start(), txt))

    for m in re.finditer(
        r'<div class="col-sm-12 team-member">\s*<div class="row">(.*?)</div>\s*</div>\s*</div>',
        html,
        re.S,
    ):
        block = m.group(1)
        # name: first <a>...</a> text, else first non-tag text in col-sm-5
        name = None
        url = None
        am = re.search(r'<a href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', block, re.S)
        col5 = re.search(r'<div class="col-sm-5">(.*?)</div>', block, re.S)
        if am:
            url = am.group(1).strip()
            name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", am.group(2))).strip()
        elif col5:
            txt = re.sub(r"<i>.*?</i>", "", col5.group(1), flags=re.S)
            name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", txt)).strip().rstrip(",")
        if not name:
            continue
        dept = None
        dm = re.search(r"<i>\s*(.*?)\s*</i>", block, re.S)
        if dm:
            dept = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", dm.group(1))).strip()
        role = None
        rm = re.search(r'<div class="col-sm-7">\s*(.*?)\s*</div>', block, re.S)
        if rm:
            role = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", rm.group(1))).strip()
        sec = ""
        for pos, txt in section_marks:
            if pos < m.start():
                sec = txt
            else:
                break
        people.append(
            {"name": name.rstrip(","), "dept": dept, "role": role, "url": url, "section": sec}
        )

    # Faculty h4 blocks (different markup at top of page)
    for m in re.finditer(r"<h4[^>]*>\s*(?:<a[^>]*>)?\s*([^<]{3,60}?)\s*(?:</a>)?\s*</h4>", html):
        nm = re.sub(r"\s+", " ", m.group(1)).strip()
        if nm and not any(
            k in nm for k in ("Group", "Connect", "links", "Affiliated", "Stanford NLP")
        ):
            people.append({"name": nm, "dept": None, "role": "Faculty", "url": None, "section": "Faculty"})
    return people


def main() -> None:
    site = parse_site()
    extra = [
        line.strip()
        for line in EXTRA.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    seen: dict[str, dict] = {}
    # (first,last)-token key -> norm key, to merge "Arun Chaganty" into
    # "Arun Tejasvi Chaganty" and "Chris Cox" into "Chris(topher) Cox"
    fl_seen: dict[str, str] = {}

    def fl(name: str) -> str | None:
        toks = norm(name).split()
        return f"{toks[0]} {toks[-1]}" if len(toks) >= 2 else None

    for p in site:
        c = canonical(p["name"])
        key = norm(c)
        if key not in seen:
            seen[key] = {
                "name": c,
                "source": "site",
                "dept": p.get("dept"),
                "role": p.get("role"),
                "url": p.get("url"),
                "section": p.get("section"),
            }
            k = fl(c)
            if k:
                fl_seen.setdefault(k, key)
    n_site = len(seen)
    for name in extra:
        c = canonical(name)
        key = norm(c)
        hit = key if key in seen else fl_seen.get(fl(c) or "")
        if hit and hit in seen:
            if seen[hit]["source"] == "site":
                seen[hit]["source"] = "both"
        else:
            seen[key] = {"name": c, "source": "list"}
            k = fl(c)
            if k:
                fl_seen.setdefault(k, key)

    roster = sorted(seen.values(), key=lambda p: p["name"].split()[-1].casefold())
    OUT.write_text(json.dumps(roster, indent=1, ensure_ascii=False))
    n_both = sum(1 for p in roster if p["source"] == "both")
    print(
        f"site people: {n_site}  extra-list only: {len(roster) - n_site}  "
        f"overlap: {n_both}  total: {len(roster)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

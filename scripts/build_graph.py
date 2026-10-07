#!/usr/bin/env python3
"""Assemble public/graph.json from the crawled Scholar data.

Papers are identified by normalized title (+/-1 year tolerance when
clustering). Two kinds of evidence put a roster person on a paper:
  1. the paper appears on their own Scholar profile  (strong)
  2. another roster member's copy of the paper lists them in the (possibly
     truncated) author string, matched by first-initial + surname, counted
     only when that key is unique within the roster  (good enough)
Only papers connecting >= 2 roster people ship to the client.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from common import ALT_NAMES, DATA, ROOT, load_json, norm, strip_accents

PUBS_DIR = DATA / "pubs"
OUT = ROOT / "public" / "graph.json"

TITLE_STOP = {
    "introduction", "preface", "editorial", "erratum", "corrigendum",
    "appendix", "index", "abstract", "discussion", "reply", "response",
}

# Surnames too common for initial+surname matching to be trusted: "D Chen"
# on some JAMA letter is NOT Danqi. People with these surnames only join a
# paper via their own Scholar profile or a written-out full-name match.
COMMON_SURNAMES = {
    "chen", "wang", "li", "zhang", "liu", "lee", "kim", "park", "wu",
    "zhou", "yang", "lin", "xu", "sun", "huang", "hu", "he", "gao", "zhao",
    "smith", "johnson", "jones", "brown", "davis", "wilson", "taylor",
    "clark", "lewis", "walker", "hall", "young", "king", "cox", "singh",
    "kumar", "gupta", "shah", "patel", "khan", "ali",
}


JUNK_TAIL = {
    "arxiv", "doi", "preprint", "org", "url", "https", "http", "vol",
    "pp", "abs", "corr", "available", "online",
}


def title_key(t: str) -> str | None:
    # strip a leading citation fragment: "& Liang, P.(2022). Actual title…"
    t = re.sub(r"^\s*&?\s*[A-Z][\w-]+,\s*[A-Z]\.?,?\s*(\(\d{4}\))?\.?\s*", "", t)
    toks = norm(t).split()
    # strip citation cruft off the tail: trailing arXiv/DOI refs and years
    popped_junk = False
    while toks:
        tail = toks[-1]
        if tail in JUNK_TAIL:
            popped_junk = True
            toks.pop()
        elif re.fullmatch(r"(19|20)\d\d", tail):
            toks.pop()
        elif popped_junk and re.fullmatch(r"\d{1,6}", tail):
            toks.pop()
        else:
            break
    k = " ".join(toks)
    if not k or k in TITLE_STOP or len(toks) < 2 or len(k) < 8:
        return None
    if k.startswith("proceedings of") or k.startswith("proceedings the"):
        return None
    return k


def year_of(p: dict) -> int | None:
    y = p.get("year")
    if y and re.fullmatch(r"\d{4}", str(y)):
        return int(y)
    return None


def main() -> None:
    roster = load_json(DATA / "roster.json", [])
    ids = load_json(DATA / "scholar_ids.json", {})
    profs_raw = load_json(DATA / "stanford_profs.json", {"profs": []})["profs"]

    people = sorted(roster, key=lambda p: norm(p["name"]))
    key2idx = {norm(p["name"]): i for i, p in enumerate(people)}

    # --- author-string matcher: (first initial, surname) -> person idx -----
    by_initial_last: dict[tuple[str, str], set[int]] = defaultdict(set)
    for i, p in enumerate(people):
        for nm in [p["name"]] + ALT_NAMES.get(p["name"], []):
            toks = norm(nm).split()
            if len(toks) < 2:
                continue
            # surname = last token, and also last-two tokens for the "de
            # marneffe" crowd; initial = first letter of first token
            by_initial_last[(toks[0][0], toks[-1])].add(i)
            if len(toks) >= 3:
                by_initial_last[(toks[0][0], " ".join(toks[-2:]))].add(i)
    uniq_il = {k: next(iter(v)) for k, v in by_initial_last.items() if len(v) == 1}

    def match_author_token(tok: str) -> int | None:
        # tokens look like "CD Manning", "J Finkel", "MC De Marneffe",
        # occasionally a full "Jenny Rose Finkel"
        t = norm(tok)
        parts = t.split()
        if len(parts) < 2:
            return None
        full = key2idx.get(t)
        if full is not None:
            return full
        initial = parts[0][0]
        for surlen in (2, 1):
            if len(parts) >= 1 + surlen:
                sur = " ".join(parts[-surlen:])
                if sur in COMMON_SURNAMES:
                    continue
                key = (initial, sur)
                if key in uniq_il:
                    return uniq_il[key]
        return None

    # --- cluster rows into papers ------------------------------------------
    # clusters[title_key] = list of {years:set, participants:set, best:(row)}
    clusters: dict[str, list[dict]] = defaultdict(list)
    n_rows = 0
    for f in sorted(PUBS_DIR.glob("*.json")):
        owner = key2idx.get(f.stem)
        if owner is None:
            continue
        for row in json.loads(f.read_text())["pubs"]:
            tk = title_key(row["title"])
            if tk is None:
                continue
            n_rows += 1
            y = year_of(row)
            bucket = None
            for c in clusters[tk]:
                if y is None or not c["years"] or any(abs(y - cy) <= 1 for cy in c["years"]):
                    bucket = c
                    break
            if bucket is None:
                bucket = {"years": set(), "participants": set(), "rows": []}
                clusters[tk].append(bucket)
            if y is not None:
                bucket["years"].add(y)
            bucket["participants"].add(owner)
            bucket["rows"].append(row)
            # author-string supplement
            for tok in row.get("authors", "").split(","):
                tok = tok.strip().rstrip(". ")
                if not tok or tok == "...":
                    continue
                m = match_author_token(tok)
                if m is not None:
                    bucket["participants"].add(m)

    # --- second pass: fold citation-mangled fragments into big papers ------
    # "& Bernstein, MS (2021). On the opportunities and risks of foundation
    # models" still contains the real title; if a well-attested paper's key
    # is a substring of a lesser key, they are the same paper.
    anchors = [
        (tk, c)
        for tk, buckets in clusters.items()
        for c in buckets
        if len(c["participants"]) >= 8 and len(tk) >= 25
    ]
    for tk, buckets in list(clusters.items()):
        for c in buckets:
            for atk, ac in anchors:
                if c is ac or atk == tk:
                    continue
                if atk in tk:
                    y, ay = (min(c["years"]) if c["years"] else None), (
                        min(ac["years"]) if ac["years"] else None
                    )
                    if y is None or ay is None or abs(y - ay) <= 2:
                        ac["participants"] |= c["participants"]
                        ac["years"] |= c["years"]
                        ac["rows"] += c["rows"]
                        c["participants"] = set()  # tombstone
                    break

    # --- emit ---------------------------------------------------------------
    papers = []
    deg = defaultdict(int)
    for tk, buckets in clusters.items():
        for c in buckets:
            if len(c["participants"]) < 2:
                continue
            # display title: shortest raw title (citation-mangled variants
            # run long); authors/venue: longest author string (least truncated)
            best_t = min(c["rows"], key=lambda r: len(r.get("title", "") or "~" * 999))
            best_a = max(c["rows"], key=lambda r: len(r.get("authors", "")))
            year = min(c["years"]) if c["years"] else None
            parts = sorted(c["participants"])
            papers.append(
                {
                    "t": best_t["title"],
                    "y": year,
                    "v": best_a.get("venue") or None,
                    "a": best_a.get("authors") or None,
                    "p": parts,
                }
            )
            for pi in parts:
                deg[pi] += 1
    papers.sort(key=lambda r: (r["y"] or 0, norm(r["t"])))

    prof_by_key = {}
    for pr in profs_raw:
        prof_by_key[norm(pr["name"])] = [pr["start"], pr["end"]]

    out_people = []
    for i, p in enumerate(people):
        entry: dict = {"name": p["name"]}
        k = norm(p["name"])
        if k == "christopher manning":
            entry["m"] = 1
        if k in prof_by_key:
            entry["prof"] = prof_by_key[k]
        if k in ids:
            entry["g"] = ids[k]["user"]
        out_people.append(entry)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"people": out_people, "papers": papers}, ensure_ascii=False, separators=(",", ":"))
    )

    linked = sum(1 for i in range(len(people)) if deg[i])
    print(f"rows scanned:       {n_rows}")
    print(f"people:             {len(people)} ({linked} with >=1 linking paper)")
    print(f"linking papers:     {len(papers)}")
    print(f"graph.json size:    {OUT.stat().st_size / 1e6:.2f} MB")
    top = sorted(deg.items(), key=lambda kv: -kv[1])[:8]
    for pi, d in top:
        print(f"   hub: {people[pi]['name']:<30} {d} linking papers")
    iso = [people[i]["name"] for i in range(len(people)) if not deg[i]]
    print(f"isolated ({len(iso)}): {', '.join(iso[:25])}{' …' if len(iso) > 25 else ''}")


if __name__ == "__main__":
    main()

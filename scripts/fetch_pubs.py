#!/usr/bin/env python3
"""Fetch every publication (title, year, author string, venue) for each
resolved Scholar profile, via the public profile pages:

    citations?user=ID&hl=en&cstart=K&pagesize=100

Writes data/pubs/{norm_name}.json; skips people already fetched, so it is
safe to rerun after a block or crash.
"""
import html as H
import re
import sys

from common import DATA, Blocked, load_json, norm, save_json, scholar_fetch

IDS = load_json(DATA / "scholar_ids.json", {})
PUBS_DIR = DATA / "pubs"

ROW_RE = re.compile(
    r'<tr class="gsc_a_tr">.*?class="gsc_a_at"[^>]*>(?P<title>.*?)</a>'
    r'.*?<div class="gs_gray">(?P<authors>.*?)</div>'
    r'\s*<div class="gs_gray">(?P<venue>.*?)</div>'
    r'.*?class="gsc_a_h gsc_a_hc gs_ibl">(?P<year>[^<]*)</span>',
    re.S,
)


def clean(s: str) -> str:
    s = re.sub(r"<span class=\"gs_oph\">.*?</span>", "", s)
    return H.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def fetch_person(key: str, user: str) -> list[dict]:
    pubs = []
    cstart = 0
    while True:
        url = (
            f"https://scholar.google.com/citations?user={user}"
            f"&hl=en&cstart={cstart}&pagesize=100"
        )
        body = scholar_fetch(url)
        rows = list(ROW_RE.finditer(body))
        for m in rows:
            pubs.append(
                {
                    "title": clean(m.group("title")),
                    "authors": clean(m.group("authors")),
                    "venue": clean(m.group("venue")),
                    "year": clean(m.group("year")) or None,
                }
            )
        if len(rows) < 100:
            break
        cstart += 100
        if cstart >= 3000:  # safety stop
            break
    return pubs


def main() -> None:
    PUBS_DIR.mkdir(parents=True, exist_ok=True)
    todo = [(k, v["user"]) for k, v in IDS.items() if not (PUBS_DIR / f"{k}.json").exists()]
    print(f"{len(todo)} profiles to fetch ({len(IDS) - len(todo)} already done)", flush=True)
    for i, (key, user) in enumerate(todo):
        fname = PUBS_DIR / f"{key}.json"
        try:
            pubs = fetch_person(key, user)
        except Blocked as e:
            print(f"hard block at {key}: {e} — rerun to resume", flush=True)
            sys.exit(2)
        save_json(fname, {"user": user, "pubs": pubs})
        print(f"[{i + 1}/{len(todo)}] {key}: {len(pubs)} pubs", flush=True)


if __name__ == "__main__":
    main()

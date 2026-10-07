#!/usr/bin/env python3
"""Resolve Google Scholar user IDs for everyone in data/roster.json.

Scholar's author-search endpoint now requires a Google login, so instead:
  stage A: crawl each person's homepage (from the NLP people page) looking
           for a scholar.google.com/citations?user=... link
  stage B: BFS over Scholar "co-authors" listings starting from the people
           we already know, matching listed names against the roster

Writes data/scholar_ids.json  {norm_name: {user, scholar_name, how}}
Resumable; reruns skip finished work.
"""
import html as H
import re
import sys
from pathlib import Path

from common import (
    ALT_NAMES,
    DATA,
    Blocked,
    fetch,
    fl_key,
    load_json,
    norm,
    save_json,
    scholar_fetch,
)

ROSTER = load_json(DATA / "roster.json", [])
OUT = DATA / "scholar_ids.json"
STATE = DATA / "raw" / "resolve_state.json"

SEEDS = {"christopher manning": ("1zmDOdwAAAAJ", "Christopher D Manning")}


def roster_matchers():
    """exact-norm map and (first,last) map -> roster norm key."""
    exact: dict[str, str] = {}
    fl: dict[str, list[str]] = {}
    for p in ROSTER:
        key = norm(p["name"])
        names = [p["name"]] + ALT_NAMES.get(p["name"], [])
        for n in names:
            exact.setdefault(norm(n), key)
            k = fl_key(n)
            if k:
                fl.setdefault(k, [])
                if key not in fl[k]:
                    fl[k].append(key)
    return exact, fl


EXACT, FL = roster_matchers()


def match_roster(scholar_name: str) -> str | None:
    n = norm(scholar_name)
    if n in EXACT:
        return EXACT[n]
    k = fl_key(scholar_name)
    if k and k in FL and len(FL[k]) == 1:
        return FL[k][0]
    return None


def parse_profiles(html: str) -> list[tuple[str, str]]:
    """(scholar display name, user id) pairs from any Scholar listing page."""
    out = []
    for m in re.finditer(
        r'gs_ai_name"><a href="[^"]*user=([\w-]{12})[^"]*"[^>]*>(.*?)</a>', html, re.S
    ):
        name = H.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        out.append((name, m.group(1)))
    return out


def main() -> None:
    ids = load_json(OUT, {})
    state = load_json(STATE, {"home_done": [], "coll_done": []})

    for k, (user, sname) in SEEDS.items():
        ids.setdefault(k, {"user": user, "scholar_name": sname, "how": "seed"})

    # ---- stage A: homepages --------------------------------------------
    todo = [
        p
        for p in ROSTER
        if p.get("url")
        and norm(p["name"]) not in ids
        and p["url"] not in state["home_done"]
    ]
    print(f"stage A: {len(todo)} homepages to try", flush=True)
    for i, p in enumerate(todo):
        url = p["url"]
        try:
            if url.startswith("/"):
                url = "https://nlp.stanford.edu" + url
            direct = re.search(r"scholar\.google\.[a-z.]+/citations\?[^\"'<>]*user=([\w-]{12})", url)
            if direct:
                ids[norm(p["name"])] = {
                    "user": direct.group(1),
                    "scholar_name": p["name"],
                    "how": "homepage-is-scholar-link",
                }
                print(f"  [A] {p['name']} -> {direct.group(1)} (direct)", flush=True)
                state["home_done"].append(p["url"])
                continue
            body = fetch(url, timeout=12)
            m = re.search(r"scholar\.google\.[a-z.]+/citations\?[^\"'<>]*user=([\w-]{12})", body)
            if m:
                ids[norm(p["name"])] = {
                    "user": m.group(1),
                    "scholar_name": p["name"],
                    "how": f"homepage:{url}",
                }
                print(f"  [A] {p['name']} -> {m.group(1)}", flush=True)
        except Exception:
            pass
        state["home_done"].append(p["url"])
        if i % 10 == 0:
            save_json(OUT, ids)
            save_json(STATE, state)
    save_json(OUT, ids)
    save_json(STATE, state)
    print(f"after stage A: {len(ids)} resolved", flush=True)

    # ---- stage B: co-author BFS ----------------------------------------
    rounds = 0
    while rounds < 6:
        rounds += 1
        queue = [
            (k, v["user"])
            for k, v in ids.items()
            if v["user"] not in state["coll_done"]
        ]
        if not queue:
            break
        print(f"stage B round {rounds}: scanning {len(queue)} colleague lists", flush=True)
        for k, user in queue:
            url = f"https://scholar.google.com/citations?view_op=list_colleagues&hl=en&user={user}"
            try:
                body = scholar_fetch(url)
            except Blocked as e:
                print(f"hard block, saving state: {e}", flush=True)
                save_json(OUT, ids)
                save_json(STATE, state)
                sys.exit(2)
            for sname, suid in parse_profiles(body):
                rkey = match_roster(sname)
                if rkey and rkey not in ids:
                    ids[rkey] = {"user": suid, "scholar_name": sname, "how": f"colleague-of:{k}"}
                    print(f"  [B] {sname} -> {suid}  (roster: {rkey})", flush=True)
            state["coll_done"].append(user)
            save_json(OUT, ids)
            save_json(STATE, state)

    unresolved = [p["name"] for p in ROSTER if norm(p["name"]) not in ids]
    print(f"\nresolved {len(ids)}/{len(ROSTER)}; unresolved ({len(unresolved)}):", flush=True)
    for n in unresolved:
        print("  -", n, flush=True)


if __name__ == "__main__":
    main()

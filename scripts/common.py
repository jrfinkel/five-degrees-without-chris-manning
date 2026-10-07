#!/usr/bin/env python3
"""Shared helpers for the Google Scholar crawl."""
import json
import random
import re
import sys
import time
import unicodedata
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

# People whose Scholar name differs from the roster name, or who publish
# under variants. canonical roster name -> list of alternate names.
ALT_NAMES: dict[str, list[str]] = {
    "Christopher Manning": ["Christopher D Manning", "Chris Manning", "Christopher D. Manning"],
    "Christopher Potts": ["Chris Potts"],
    "Dan Jurafsky": ["Daniel Jurafsky"],
    "Jenny Finkel": ["Jenny Rose Finkel", "Jenny R Finkel", "Jenny Rose Finkel Mason"],
    "Julia (Neidert) Neizonek": ["Julia Neidert", "Julia Neizonek"],
    "Thang Luong": ["Minh-Thang Luong", "Minh Thang Luong"],
    "Samuel Bowman": ["Sam Bowman", "Samuel R Bowman", "Samuel R. Bowman"],
    "Ed Chi": ["Ed H Chi", "Ed H. Chi", "Ed Huai-hsin Chi", "E Chi"],
    "Robert Monarch": ["Robert Munro", "Robert (Munro) Monarch", "Rob Munro"],
    "Marie-Catherine de Marneffe": ["Marie-Catherine de Marneffe", "Marie Catherine de Marneffe"],
    "David Hall": ["David LW Hall", "David L W Hall"],
    "Natalia Silveira": ["Natália Silveira"],
    "Sebastian Padó": ["Sebastian Pado"],
    "Tolúlọpẹ́ Ògúnrẹ̀mí": ["Tolulope Ogunremi"],
    "Daniel Ramage": ["Dan Ramage"],
    "Mihail Eric": ["Mihail Eri\u0107"],
    "Victor Zhong": ["Victor W Zhong"],
    "Michel Galley": ["M Galley"],
    "Abi See": ["Abigail See"],
    "Nate Chambers": ["Nathanael Chambers"],
    "Sharon Goldwater": ["Sharon J Goldwater"],
}


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def norm(name: str) -> str:
    s = strip_accents(name).casefold()
    s = re.sub(r"[.\u2019'()]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def fl_key(name: str) -> str | None:
    toks = norm(name).split()
    if len(toks) < 2:
        return None
    return toks[0] + " " + toks[-1]


class Blocked(Exception):
    pass


def fetch(url: str, timeout: int = 25, opener=None) -> str:
    """GET a URL; raise Blocked when Scholar walls us off."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    open_fn = opener.open if opener else urllib.request.urlopen
    try:
        with open_fn(req, timeout=timeout) as r:
            final = r.geturl()
            body = r.read(3_000_000).decode("utf-8", "replace")  # 3MB cap
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise Blocked(f"HTTP {e.code} on {url}")
        raise
    if "accounts.google.com" in final or "/sorry/" in final:
        raise Blocked(f"redirected to {final[:80]}")
    if "gs_captcha" in body or "unusual traffic from your computer" in body:
        raise Blocked(f"captcha on {url}")
    return body


# ---------------------------------------------------------------------------
# Optional SOAX proxy for Scholar traffic (SOAX_SCHOLAR=1).
# Reuses the zeitgeist package via its shared-config pointer, but targets it
# DIFFERENTLY on purpose: country-level geo only (zeitgeist pins per-city
# sessions for its AdsPower profiles) and a separate "degree…" session-id
# prefix, so nothing here can collide with that repo's sticky exits.
# A fresh session id = a fresh mobile exit IP, so a 429 costs seconds, not
# minutes of backoff.
# ---------------------------------------------------------------------------
import os
import string

_soax_block = None
_opener = None
_opener_reqs = 0
_SESSION_RECYCLE = 60  # proactively hop exits every N requests


def _soax_conf():
    global _soax_block
    if _soax_block is None:
        loc = json.loads((Path.home() / "zeitgeist" / "config-location.json").read_text())
        cfg = Path(loc["configDir"].replace("~", str(Path.home()), 1))
        _soax_block = json.loads((cfg / "secrets.json").read_text())["soax-mobile"]
    return _soax_block


def _mint_opener(log=print):
    """New SOAX session (= new exit IP), verified live before use."""
    global _opener, _opener_reqs
    from urllib.parse import quote

    b = _soax_conf()
    geo = os.environ.get("SOAX_GEO", "country-us")
    for _ in range(4):
        sid = "degree" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        user = b["user"].replace("{geo}", geo).replace("{session}", sid)
        purl = f"http://{quote(user, safe='')}:{quote(b['password'], safe='')}@{b['host']}:{b['port']}"
        cand = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": purl, "https": purl})
        )
        try:  # dead-session guard: one clean CONNECT before we trust it
            req = urllib.request.Request(
                "https://ip.oxylabs.io/location", headers={"User-Agent": UA}
            )
            with cand.open(req, timeout=20) as r:
                r.read(20000)
            _opener, _opener_reqs = cand, 0
            log(f"proxy session {sid} live", flush=True)
            return
        except Exception as e:
            log(f"proxy session {sid} dead on arrival ({type(e).__name__}); reminting", flush=True)
    raise Blocked("could not mint a live SOAX session")


def scholar_fetch(url: str, log=print) -> str:
    """fetch() with jitter; proxied via SOAX when SOAX_SCHOLAR=1 (fresh
    session on every block) or plain with long backoffs otherwise.
    Returns "" for pages that simply don't exist (404 = e.g. a profile with
    no public co-author list)."""
    global _opener_reqs
    proxied = os.environ.get("SOAX_SCHOLAR") == "1"
    lo = float(os.environ.get("SCHOLAR_DELAY_MIN", "1.2" if proxied else "2.2"))
    hi = float(os.environ.get("SCHOLAR_DELAY_MAX", "2.6" if proxied else "4.2"))
    time.sleep(random.uniform(lo, hi))
    attempts = 7 if proxied else 4
    for attempt in range(attempts):
        try:
            if proxied:
                if _opener is None or _opener_reqs >= _SESSION_RECYCLE:
                    _mint_opener(log)
                _opener_reqs += 1
                return fetch(url, opener=_opener)
            return fetch(url)
        except Blocked as e:
            if proxied:
                log(f"blocked ({e}); hopping to a fresh exit", flush=True)
                time.sleep(random.uniform(4, 9))
                _mint_opener(log)
            else:
                wait = 90 * (attempt + 1)
                log(f"BLOCKED ({e}); sleeping {wait}s", flush=True)
                time.sleep(wait)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            if proxied and e.code in (502, 522, 525):
                # gateway minted us a dud exit; hop
                log(f"gateway {e.code}; hopping to a fresh exit", flush=True)
                _mint_opener(log)
                continue
            log(f"http {e.code} ({url}); retrying in 20s", flush=True)
            time.sleep(20)
        except Exception as e:
            log(f"error ({e}); retrying in {'5' if proxied else '20'}s", flush=True)
            time.sleep(5 if proxied else 20)
    raise Blocked(f"gave up on {url}")


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False))
    tmp.replace(path)

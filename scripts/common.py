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
    "Jenny Finkel": ["Jenny Rose Finkel", "Jenny R Finkel"],
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


def fetch(url: str, timeout: int = 25) -> str:
    """GET a URL; raise Blocked when Scholar walls us off."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
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


def scholar_fetch(url: str, log=print) -> str:
    """fetch() with jitter + backoff for scholar.google.com."""
    time.sleep(random.uniform(2.2, 4.2))
    for attempt in range(4):
        try:
            return fetch(url)
        except Blocked as e:
            wait = 90 * (attempt + 1)
            log(f"BLOCKED ({e}); sleeping {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            log(f"error ({e}); retrying in 20s", flush=True)
            time.sleep(20)
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

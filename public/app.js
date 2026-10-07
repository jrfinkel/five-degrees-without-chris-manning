// 5 Degrees Without Chris Manning — client logic.
// Pure ES module: the pathfinding core is exported so node can unit-test the
// exact code that ships to browsers.

// ---------------------------------------------------------------------------
// Pathfinding
// ---------------------------------------------------------------------------

/** Was person p a Stanford professor in year y (null year = unknown)? */
export function profAt(p, y) {
  if (!p.prof) return false;
  if (y == null) return true; // unknown year: be strict
  return y >= p.prof[0] && (p.prof[1] == null || y <= p.prof[1]);
}

/**
 * BFS over the bipartite person/paper graph.
 * G: {people, papers, adj}  adj[i] = paper indexes for person i.
 * opts: {allowManning: false, strict: false}
 * An intermediate person may not be Manning (unless allowManning) and, in
 * strict mode, may not have been a Stanford prof in the year of EITHER paper
 * adjacent to them in the chain. Endpoints are always exempt.
 * Returns {found, people: [personIdx...], papers: [paperIdx...]} where
 * people.length === papers.length + 1.
 */
export function findPath(G, a, b, opts = {}) {
  if (a === b) return { found: true, people: [a], papers: [] };
  const ok = (pi, paper) => {
    if (pi === a || pi === b) return true;
    const p = G.people[pi];
    if (p.m && !opts.allowManning) return false;
    if (opts.strict && profAt(p, paper.y)) return false;
    return true;
  };
  const prev = new Map(); // personIdx -> [prevPersonIdx, viaPaperIdx]
  const seenPaper = new Uint8Array(G.papers.length);
  let frontier = [a];
  prev.set(a, null);
  while (frontier.length) {
    const next = [];
    for (const x of frontier) {
      for (const ri of G.adj[x] || []) {
        if (seenPaper[ri]) continue;
        const paper = G.papers[ri];
        if (!ok(x, paper)) continue; // x leaves via this paper
        seenPaper[ri] = 1;
        for (const q of paper.p) {
          if (prev.has(q)) continue;
          if (!ok(q, paper)) continue; // q enters via this paper
          prev.set(q, [x, ri]);
          if (q === b) return unwind(prev, b);
          next.push(q);
        }
      }
    }
    frontier = next;
  }
  return { found: false };
}

function unwind(prev, b) {
  const people = [b];
  const papers = [];
  let cur = b;
  while (true) {
    const step = prev.get(cur);
    if (!step) break;
    papers.push(step[1]);
    people.push(step[0]);
    cur = step[0];
  }
  people.reverse();
  papers.reverse();
  return { found: true, people, papers };
}

/** Build person->papers adjacency once. */
export function buildAdj(G) {
  const adj = Array.from({ length: G.people.length }, () => []);
  G.papers.forEach((paper, ri) => {
    for (const pi of paper.p) adj[pi].push(ri);
  });
  G.adj = adj;
  return G;
}

// ---------------------------------------------------------------------------
// UI (skipped under node)
// ---------------------------------------------------------------------------
if (typeof document !== "undefined") init();

async function init() {
  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  const fold = (s) =>
    s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

  let G;
  try {
    G = await (await fetch("/graph.json")).json();
  } catch (e) {
    $("status").textContent = "failed to load graph.json";
    return;
  }
  buildAdj(G);
  const npap = G.papers.length;
  $("status").textContent = `${G.people.length} people · ${npap} linking papers`;
  const np = $("npeople");
  if (np) np.textContent = String(G.people.length);

  const folded = G.people.map((p) => fold(p.name));
  let strict = false;
  const sel = { pa: -1, pb: -1 };

  // ----- comboboxes -----
  for (const [inputId, listId, key] of [["pa", "la", "pa"], ["pb", "lb", "pb"]]) {
    const input = $(inputId);
    const list = $(listId);
    let hot = 0;
    let items = [];

    const show = () => {
      const q = fold(input.value.trim());
      items = [];
      if (q) {
        for (let i = 0; i < folded.length && items.length < 12; i++) {
          if (folded[i].includes(q)) items.push(i);
        }
      }
      hot = 0;
      list.innerHTML = items
        .map((i, k) => {
          const p = G.people[i];
          const extra = (G.adj[i] || []).length
            ? `<span class="muted small"> · ${G.adj[i].length} linking papers</span>`
            : `<span class="nopub small"> · no linked pubs</span>`;
          return `<div data-i="${i}" class="${k === 0 ? "hot" : ""}">${esc(p.name)}${extra}</div>`;
        })
        .join("");
      list.style.display = items.length ? "block" : "none";
    };
    const choose = (i) => {
      sel[key] = i;
      input.value = G.people[i].name;
      list.style.display = "none";
    };
    input.addEventListener("input", () => { sel[key] = -1; show(); });
    input.addEventListener("focus", show);
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!items.length) return;
        hot = (hot + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length;
        [...list.children].forEach((el, k) => el.classList.toggle("hot", k === hot));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (items.length) choose(items[hot]);
      } else if (e.key === "Escape") {
        list.style.display = "none";
      }
    });
    list.addEventListener("mousedown", (e) => {
      const d = e.target.closest("div[data-i]");
      if (d) choose(+d.dataset.i);
    });
    document.addEventListener("click", (e) => {
      if (!list.contains(e.target) && e.target !== input) list.style.display = "none";
    });
  }

  // ----- strict toggle -----
  const strictEl = $("strict");
  const setStrict = (v) => {
    strict = v;
    strictEl.querySelector(".box").textContent = v ? "[X]" : "[ ]";
    strictEl.setAttribute("aria-checked", String(v));
  };
  strictEl.addEventListener("click", () => setStrict(!strict));
  strictEl.addEventListener("keydown", (e) => {
    if (e.key === " " || e.key === "Enter") { e.preventDefault(); setStrict(!strict); }
  });

  // ----- rendering -----
  const personBox = (pi, { endpoint, offenderTag } = {}) => {
    const p = G.people[pi];
    const cls = endpoint ? "person endpoint" : offenderTag ? "person offender" : "person";
    const tag = offenderTag ? `<br><span class="tag">${esc(offenderTag)}</span>` : "";
    return `<div class="${cls}">${esc(p.name)}${tag}</div>`;
  };
  const paperBox = (ri) => {
    const r = G.papers[ri];
    const meta = [r.a, r.v, r.y ?? "year unknown"].filter(Boolean).join(" · ");
    return `<div class="paper"><span class="t">${esc(r.t)}</span><br><span class="meta">${esc(meta)}</span></div>`;
  };

  function renderPath(res, { verdict, fail, note, offenders } = {}) {
    const deg = res.papers.length;
    let h = `<div class="verdict ${fail ? "fail" : ""}">${verdict}` +
      (note ? `<span class="small">${note}</span>` : "") + `</div><div class="chain">`;
    res.people.forEach((pi, k) => {
      const off = offenders && offenders.get(pi);
      h += personBox(pi, { endpoint: k === 0 || k === res.people.length - 1, offenderTag: off });
      if (k < res.papers.length) h += paperBox(res.papers[k]);
    });
    const nManning = res.people.filter((pi) => G.people[pi].m).length;
    h += `</div><div class="statgrid">
      <div class="stat"><div class="n">${deg}</div><div class="l">degrees</div></div>
      <div class="stat"><div class="n">${res.people.length - 2 < 0 ? 0 : res.people.length - 2}</div><div class="l">intermediaries</div></div>
      <div class="stat"><div class="n"${nManning ? ' style="color:var(--bad)"' : ""}>${nManning}</div><div class="l">mannings</div></div>
    </div>`;
    return h;
  }

  function diagnose(a, b) {
    // why did we fail? try relaxing constraints in order of scandal
    if (strict) {
      const noStrict = findPath(G, a, b, { strict: false });
      if (noStrict.found) {
        const offenders = new Map();
        noStrict.people.forEach((pi, k) => {
          if (k === 0 || k === noStrict.people.length - 1) return;
          const yIn = G.papers[noStrict.papers[k - 1]].y;
          const yOut = G.papers[noStrict.papers[k]].y;
          const p = G.people[pi];
          if (profAt(p, yIn) || profAt(p, yOut)) {
            offenders.set(pi, `STANFORD PROF ${p.prof[0]}–${p.prof[1] ?? "now"}`);
          }
        });
        return renderPath(noStrict, {
          verdict: "BLOCKED BY THE FACULTY",
          fail: true,
          note: "every shortest route hires a Stanford professor as a go-between — strict mode forbids it. exhibit A:",
          offenders,
        });
      }
    }
    const viaManning = findPath(G, a, b, { allowManning: true, strict: false });
    if (viaManning.found) {
      const offenders = new Map();
      viaManning.people.forEach((pi) => {
        if (G.people[pi].m) offenders.set(pi, "THE FORBIDDEN NODE");
      });
      return renderPath(viaManning, {
        verdict: "MANNING DETECTED",
        fail: true,
        note: "these two humans are only connected through Christopher Manning. the rules are the rules. the offending route:",
        offenders,
      });
    }
    return `<div class="verdict fail">NO CONNECTION<span class="small">not even Chris Manning can save this pair — they live in different publication universes.</span></div>`;
  }

  function run() {
    const { pa: a, pb: b } = sel;
    const out = $("out");
    if (a < 0 || b < 0) {
      out.innerHTML = `<div class="flash err">pick two people first (choose from the dropdown)</div>`;
      return;
    }
    const url = new URL(location.href);
    url.searchParams.set("a", G.people[a].name);
    url.searchParams.set("b", G.people[b].name);
    strict ? url.searchParams.set("strict", "1") : url.searchParams.delete("strict");
    history.replaceState(null, "", url);

    if (a === b) {
      out.innerHTML = `<div class="verdict">0 DEGREES<span class="small">that is the same person. reflexivity is free.</span></div>`;
      return;
    }
    for (const [pi, label] of [[a, "A"], [b, "B"]]) {
      if (!(G.adj[pi] || []).length) {
        out.innerHTML = `<div class="verdict fail">NO DATA<span class="small">no linking publications found for ${esc(G.people[pi].name)} (person ${label}) — Google Scholar knows them not, or nothing they wrote links into this crowd.</span></div>`;
        return;
      }
    }
    const res = findPath(G, a, b, { strict });
    if (!res.found) {
      out.innerHTML = diagnose(a, b);
      return;
    }
    const deg = res.papers.length;
    const over = deg > 5;
    out.innerHTML = renderPath(res, {
      verdict: over ? `${deg} DEGREES — LIMIT EXCEEDED` : `CONNECTED · ${deg} DEGREE${deg === 1 ? "" : "S"}`,
      fail: over,
      note: over
        ? "more than 5 degrees without Chris Manning. honestly, impressive."
        : strict
          ? "no Mannings, no Stanford professors. squeaky clean."
          : "and not a single Manning along the way.",
    });
  }

  $("go").addEventListener("click", run);

  $("lucky").addEventListener("click", () => {
    const withPubs = G.people.map((_, i) => i).filter((i) => (G.adj[i] || []).length && !G.people[i].m);
    for (let t = 0; t < 30; t++) {
      const a = withPubs[(Math.random() * withPubs.length) | 0];
      const b = withPubs[(Math.random() * withPubs.length) | 0];
      if (a === b) continue;
      const r = findPath(G, a, b, { strict });
      if (r.found && r.papers.length >= 2) {
        sel.pa = a; sel.pb = b;
        $("pa").value = G.people[a].name;
        $("pb").value = G.people[b].name;
        run();
        return;
      }
    }
  });

  // ----- deep link -----
  const qs = new URLSearchParams(location.search);
  if (qs.get("strict") === "1") setStrict(true);
  const byName = (n) => G.people.findIndex((p) => fold(p.name) === fold(n || ""));
  const qa = byName(qs.get("a"));
  const qb = byName(qs.get("b"));
  if (qa >= 0) { sel.pa = qa; $("pa").value = G.people[qa].name; }
  if (qb >= 0) { sel.pb = qb; $("pb").value = G.people[qb].name; }
  if (qa >= 0 && qb >= 0) run();
}

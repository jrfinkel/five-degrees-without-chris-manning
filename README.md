# 5 Degrees Without Chris Manning

A riff on Six Degrees of Kevin Bacon for the Stanford NLP universe. Pick two
people; the site finds the shortest chain of co-authored papers connecting
them — with one iron rule: **Christopher Manning can never be the
connection.** You may travel *to* him; you may never travel *through* him.

There is also a **strict mode** toggle: anyone who was a Stanford professor
*at the time a paper was published* can't be a link via that paper either
(endpoints are always exempt, in both modes).

Cloudflare Worker (Hono + TypeScript), same stack and account as hive-mind,
same phosphor-and-scanlines ASCII aesthetic. No database: the co-authorship
graph ships as a static `graph.json` and the BFS runs in the browser.

## Who's in the graph

- Everyone on the [Stanford NLP people page](https://nlp.stanford.edu/people/)
  (faculty, students, postdocs, staff, visitors, alumni) at crawl time
- Plus a hand-provided list (`data/extra_people.txt`)

## Where the data comes from

Google Scholar, via each person's public profile:

1. `scripts/parse_people.py` — roster from the NLP people page + extra list
2. `scripts/resolve_ids.py` — finds Scholar profile IDs. Scholar's author
   search is login-walled now, so this crawls people's homepages for Scholar
   links, then BFSes Scholar's public "co-authors" listings from known
   profiles until no new roster members turn up
3. `scripts/fetch_pubs.py` — every publication row (title, truncated author
   string, venue, year) from each profile, 100/page; checkpointed + resumable
4. `scripts/build_graph.py` — clusters rows into papers by normalized title
   (±1 year), attaches people to papers when the paper appears on their own
   profile or when another member's author string names them unambiguously
   (first initial + surname, unique within roster). Papers linking ≥2 roster
   people ship to `public/graph.json`

Rerun everything with `npm run data` (it resumes; it does not re-crawl what
exists). Scholar rate limits: the scripts jitter 2–4 s between requests and
back off on blocks.

## Strict-mode professorship data

`data/stanford_profs.json` is hand-curated (start year of each Stanford
faculty appointment, `approx: true` where it's an educated guess from public
bios). Papers with unknown years count as *during* tenure — strict mode is
strict. Edit the file and rerun `scripts/build_graph.py` to adjust.

## Develop

```sh
npm install
npm run dev        # http://localhost:8787
node tests/pathfind.test.mjs   # BFS unit tests (tests the shipped module)
```

## Deploy

```sh
npx wrangler login # once
npm run deploy
```

## Caveats, honestly

- Google Scholar profiles are self-maintained: missing papers, missing
  people (no profile → only reachable via co-authors' author strings),
  vanity entries — all faithfully reflected
- Author strings on profile pages truncate after ~5 names, so people buried
  deep in big author lists can be missed on papers neither endpoint owns
- Identically-titled papers within a year of each other are treated as one
  paper

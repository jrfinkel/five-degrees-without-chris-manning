export const esc = (s: unknown) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!
  );

/** FIGlet-style banner. String.raw keeps the backslashes intact. */
export const BANNER = String.raw`
 ____    ____  _____  ____ ____  _____ _____ ____
| ___|  |  _ \| ____|/ ___|  _ \| ____| ____/ ___|
|___ \  | | | |  _| | |  _| |_) |  _| |  _| \___ \
 ___) | | |_| | |___| |_| |  _ <| |___| |___ ___) |
|____/  |____/|_____|\____|_| \_\_____|_____|____/
`.replace(/^\n/, "");

/**
 * Fixed background layer of star-cropped Chris Manning faces (the man you
 * must route around, watching your every path) — same scatter as hive-mind:
 * jittered 7x4 grid, shuffled per page load, mostly peeking out around the
 * opaque content cards.
 */
const FACE_SPOTS: Array<[pos: string, top: string, w: number]> = [
  ["left:-2%", "top:2%", 185],
  ["left:12%", "top:7%", 140],
  ["left:27%", "top:1%", 160],
  ["left:42%", "top:6%", 125],
  ["left:56%", "top:2%", 155],
  ["left:71%", "top:8%", 135],
  ["left:86%", "top:3%", 180],
  ["left:4%", "top:28%", 155],
  ["left:18%", "top:33%", 170],
  ["left:33%", "top:27%", 130],
  ["left:48%", "top:32%", 150],
  ["left:62%", "top:26%", 165],
  ["left:77%", "top:31%", 135],
  ["left:91%", "top:27%", 155],
  ["left:-1%", "top:54%", 165],
  ["left:14%", "top:58%", 130],
  ["left:29%", "top:52%", 155],
  ["left:44%", "top:57%", 140],
  ["left:58%", "top:53%", 170],
  ["left:73%", "top:58%", 125],
  ["left:88%", "top:52%", 160],
  ["left:7%", "top:80%", 140],
  ["left:22%", "top:84%", 160],
  ["left:37%", "top:79%", 135],
  ["left:52%", "top:84%", 155],
  ["left:66%", "top:78%", 180],
  ["left:81%", "top:83%", 130],
  ["left:94%", "top:79%", 150],
];
const FACES = Array.from({ length: 37 }, (_, i) => `/faces/star${i}.png`);

function faceLayer(): string {
  const imgs = [...FACES];
  for (let i = imgs.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [imgs[i], imgs[j]] = [imgs[j], imgs[i]];
  }
  return (
    `<div class="facestars" aria-hidden="true">` +
    FACE_SPOTS.map(
      ([pos, top, w], i) =>
        `<img src="${imgs[i % imgs.length]}" alt="" style="${pos};${top};width:${w}px">`
    ).join("") +
    `</div>`
  );
}

export function layout(o: { title: string; body: string }): string {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(o.title)}</title>
<style>${CSS}</style>
</head>
<body>
${faceLayer()}
<main id="content">${o.body}</main>
<script type="module" src="/app.js"></script>
</body>
</html>`;
}

export const CSS = `
:root {
  --bg: #030503;
  --panel: #060c06;
  --panel2: #0b150b;
  --ink: #2bff6f;
  --muted: #1c9448;
  --honey: #ffb000;
  --honey-dark: #b87d00;
  --good: #2bff6f;
  --bad: #ff4b4b;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.55 ui-monospace, Menlo, Monaco, "Cascadia Mono", "Courier New", monospace;
  text-shadow: 0 0 6px rgba(43, 255, 111, 0.28);
  overflow-x: hidden;
}
/* CRT scanlines */
body::before {
  content: ""; position: fixed; inset: 0; z-index: 9999; pointer-events: none;
  background: repeating-linear-gradient(0deg, rgba(0,0,0,0) 0 2px, rgba(0,0,0,0.22) 2px 4px);
}
/* Chris-in-stars scatter behind everything */
.facestars { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.facestars img { position: absolute; opacity: 0.18; }
/* Phones: the desktop scatter overlaps badly at ~400px wide — keep every
   third star and shrink them. */
@media (max-width: 700px) {
  .facestars img { width: 100px !important; }
  .facestars img:nth-child(3n+1), .facestars img:nth-child(3n) { display: none; }
}
main { max-width: 860px; margin: 0 auto; padding: 24px 16px 60px; position: relative; z-index: 1; }
/* ---- landscape / projector layout: controls left, results right ----- */
@media (min-width: 1100px) {
  main { max-width: 1500px; padding-top: 14px; }
  .cols { display: flex; gap: 22px; align-items: flex-start; }
  .cols > .card { flex: 0 0 450px; position: sticky; top: 14px; margin: 0; }
  .cols > #out { flex: 1 1 auto; min-width: 0; }
  .cols .pickers { display: block; }
  #out > .verdict:first-child { margin-top: 0; }
}
@media (min-width: 1400px) {
  body { font-size: 17px; }
}
a { color: var(--ink); }
h1 {
  color: var(--honey); margin: 0.4em 0; text-transform: uppercase;
  letter-spacing: 0.12em; text-shadow: 0 0 8px rgba(255,176,0,0.4);
}
h1::before { content: ">> "; color: var(--honey-dark); }
h2 { margin: 1.2em 0 0.4em; text-transform: uppercase; letter-spacing: 0.08em; }
h2::before { content: ":: "; color: var(--muted); }
.banner {
  color: var(--honey); font-size: clamp(8px, 2.1vw, 15px); line-height: 1.12;
  overflow-x: auto; margin: 12px 0 2px; text-shadow: 0 0 8px rgba(255,176,0,0.35);
  display: inline-block; text-align: left;
}
.subtitle {
  text-transform: uppercase; letter-spacing: 0.34em; margin: 0 0 18px;
  color: var(--ink); font-weight: 700;
}
.subtitle s {
  color: var(--bad); text-decoration-thickness: 2px; text-shadow: 0 0 7px rgba(255,75,75,0.45);
}
.blink::after { content: "█"; margin-left: 3px; animation: blink 1.1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.card {
  background: var(--panel); border: 1px solid var(--muted); border-radius: 0;
  padding: 18px 20px; margin: 14px 0;
}
.muted { color: var(--muted); }
.small { font-size: 0.85em; }
.center { text-align: center; }
label { display: block; font-weight: 700; margin: 12px 0 4px; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.9em; }
input[type=text] {
  width: 100%; padding: 10px 12px; border-radius: 0; border: 1px solid var(--muted);
  background: #000; color: var(--ink); font: inherit; caret-color: var(--ink);
  font-size: 16px; /* <16px makes iOS Safari zoom in on focus and stay zoomed */
}
input:focus { outline: none; border-color: var(--honey); }
.btn {
  display: inline-block; padding: 9px 20px; border: 1px solid var(--honey); border-radius: 0;
  background: var(--honey); color: #000; font: inherit; font-weight: 800;
  text-transform: uppercase; letter-spacing: 0.08em; cursor: pointer;
  text-decoration: none; text-shadow: none;
}
.btn:hover { background: #000; color: var(--honey); }
.btn.secondary { background: transparent; color: var(--ink); border-color: var(--muted); }
.btn.secondary:hover { background: var(--ink); color: #000; }
.btn-row { margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.pickers { display: flex; gap: 14px; flex-wrap: wrap; }
.pickers > div { flex: 1 1 260px; position: relative; }
.droplist {
  position: absolute; left: 0; right: 0; z-index: 30; max-height: 280px; overflow-y: auto;
  background: #000; border: 1px solid var(--honey); border-top: none; display: none;
}
.droplist div { padding: 7px 12px; cursor: pointer; }
.droplist div:hover, .droplist div.hot { background: var(--panel2); color: var(--honey); }
.droplist .nopub { color: var(--muted); }
.toggle {
  display: flex; gap: 10px; align-items: baseline; cursor: pointer; user-select: none;
  margin-top: 16px; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.9em;
}
.toggle .box { color: var(--honey); font-weight: 800; white-space: pre; }
.verdict {
  font-size: 1.5em; font-weight: 800; text-transform: uppercase; letter-spacing: 0.14em;
  padding: 16px 20px; background: #000; border: 3px double var(--honey); color: var(--honey);
  margin: 18px 0 10px; text-shadow: 0 0 10px rgba(255,176,0,0.45);
}
.verdict.fail { border-color: var(--bad); color: var(--bad); text-shadow: 0 0 10px rgba(255,75,75,0.45); }
.verdict .small { display: block; font-size: 0.55em; letter-spacing: 0.08em; margin-top: 6px; color: var(--muted); text-shadow: none; }
.chain { margin: 14px 0; }
.chain .person {
  display: inline-block; background: #000; border: 1px solid var(--ink); padding: 8px 16px;
  font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase;
}
.chain .person.endpoint { border: 3px double var(--honey); color: var(--honey); text-shadow: 0 0 8px rgba(255,176,0,0.4); }
.chain .person.offender { border-color: var(--bad); color: var(--bad); text-shadow: 0 0 8px rgba(255,75,75,0.45); }
.chain .person .tag { font-weight: 400; font-size: 0.75em; letter-spacing: 0.05em; }
.chain .hop { padding: 2px 0 2px 22px; border-left: 1px dashed var(--muted); margin-left: 18px; }
.chain .paper { padding: 10px 0 10px 22px; border-left: 1px dashed var(--muted); margin-left: 18px; position: relative; }
.chain .paper::before { content: "──"; position: absolute; left: 0; color: var(--muted); }
.chain .paper .t { font-weight: 700; }
.chain .paper .t::before { content: "■ "; color: var(--honey); }
.chain .paper .meta { color: var(--muted); font-size: 0.85em; }
.statgrid { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; }
.stat { background: #000; border: 1px solid var(--muted); border-radius: 0; padding: 10px 18px; text-align: center; }
.stat .n { font-size: 1.6em; font-weight: 800; color: var(--honey); }
.stat .l { font-size: 0.75em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
.flash { padding: 10px 14px; border-radius: 0; margin: 10px 0; background: #000; }
.flash.err { border: 1px solid var(--bad); color: var(--bad); text-shadow: none; }
.pill { display: inline-block; font-size: 0.82em; font-weight: 700; color: var(--muted); letter-spacing: 0.05em; }
.pill::before { content: "[ "; }
.pill::after { content: " ]"; }
/* QR pinned top-right beside the title, like hive-mind's name badge */
.qrcorner { position: fixed; top: 12px; right: 16px; z-index: 10; text-align: center; }
.qrcorner .qr {
  display: inline-block; background: #fff; padding: 6px; line-height: 0;
  border: 1px solid var(--muted); box-shadow: 0 0 14px rgba(43, 255, 111, 0.18);
}
.qrcorner .qr svg { width: 92px; height: 92px; display: block; }
.qrcorner .pill { display: block; margin-top: 4px; font-size: 0.72em; }
/* phones don't scan themselves */
@media (max-width: 900px) { .qrcorner { display: none; } }
footer { margin-top: 40px; color: var(--muted); font-size: 0.8em; }
`;

// 5 Degrees Without Chris Manning.
// Hono worker (same setup as hive-mind); the heavy lifting — BFS over the
// co-authorship graph — happens client-side in /app.js against /graph.json.
import { Hono } from "hono";
import { BANNER, esc, layout } from "./ui";

const app = new Hono();

app.get("/", (c) =>
  c.html(
    layout({
      title: "5 Degrees Without Chris Manning",
      body: `
<div class="center">
  <pre class="banner">${esc(BANNER)}</pre>
  <div class="subtitle">without <s>chris manning</s></div>
</div>

<div class="card">
  <p class="muted small" style="margin-top:0">
    Pick two people from the extended Stanford NLP universe. We find the
    shortest chain of co-authored papers connecting them —
    <span style="color:var(--bad)">Christopher Manning may never be a link</span>.
    Endpoints are exempt; you may travel <em>to</em> him, just never <em>through</em> him.
  </p>

  <div class="pickers">
    <div>
      <label for="pa">Person A</label>
      <input type="text" id="pa" autocomplete="off" spellcheck="false" placeholder="type a name…">
      <div class="droplist" id="la"></div>
    </div>
    <div>
      <label for="pb">Person B</label>
      <input type="text" id="pb" autocomplete="off" spellcheck="false" placeholder="type a name…">
      <div class="droplist" id="lb"></div>
    </div>
  </div>

  <div class="toggle" id="strict" role="checkbox" aria-checked="false" tabindex="0">
    <span class="box">[ ]</span>
    <span>strict mode — anyone who was a Stanford professor when the paper
      was published cannot be a link either</span>
  </div>

  <div class="btn-row">
    <button class="btn" id="go">Find path</button>
    <button class="btn secondary" id="lucky">I'm feeling disconnected</button>
    <span class="pill" id="status">loading graph<span class="blink"></span></span>
  </div>
</div>

<div id="out"></div>

<footer>
  Data: Google Scholar profiles of <span id="npeople">?</span> Stanford-NLP-adjacent humans ·
  co-authorship only counts when the paper appears on both people's own
  profiles or the author list says so · Stanford professorship years are
  curated approximations. No Mannings were harmed.
</footer>`,
    })
  )
);

export default app;

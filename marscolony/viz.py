"""Trace visualizer — a read-only consumer of traces (ADR-0001: the sim
loop is never touched). Emits a standalone HTML file with the whole episode
embedded: timeline scrubber, map, storage gauges, per-tick action verdicts,
and the raw model outputs behind each action.

Usage:  python -m marscolony visualize --trace run.trace.jsonl [--out run.html]
"""

import json
import os

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Mars Colony — trace replay</title>
<style>
:root{--bg:#0b0e14;--panel:#131826;--line:#232b3d;--tx:#c8d2e0;--dim:#6b7689;
--ok:#3fb96f;--bad:#e0555a;--acc:#4ea1ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.45 ui-monospace,Menlo,Consolas,monospace}
#wrap{max-width:1280px;margin:0 auto;padding:18px}
h1{font-size:16px;margin:0 0 2px;color:#fff}
.sub{color:var(--dim);font-size:12px;margin-bottom:14px}
#top{display:flex;gap:14px;flex-wrap:wrap}
#map{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:12px}
#grid{display:grid;gap:1px}
.cell{width:15px;height:15px;border-radius:2px;position:relative}
.tt{background:#2a2620}.tb{background:#3a3530}.ti{background:#17435e}.tc{background:#05060a}
.st{position:absolute;inset:1px;border-radius:3px}
.sbase{background:#d9a520}.spanel{background:#e07a2f}.sextractor{background:#3d7bd9}
.sgreenhouse{background:#39a95c}
.ag{position:absolute;width:11px;height:11px;border-radius:50%;top:1px;left:1px;
border:1px solid #fff;font-size:0}
.dead{opacity:.25}
#side{flex:1;min-width:340px;display:flex;flex-direction:column;gap:12px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:12px}
.lbl{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.8px}
.gauge{margin:6px 0}
.bar{height:8px;background:#1b2233;border-radius:4px;overflow:hidden}
.fill{height:100%;border-radius:4px}
.grow{display:flex;justify-content:space-between;font-size:12px}
#ctrl{display:flex;gap:10px;align-items:center;margin:14px 0}
input[type=range]{flex:1;accent-color:var(--acc)}
button{background:var(--panel);color:var(--tx);border:1px solid var(--line);
border-radius:6px;padding:5px 12px;cursor:pointer;font:inherit}
.act{margin:3px 0;font-size:12.5px}
.ok{color:var(--ok)}.bad{color:var(--bad)}
.raw{background:#0d1119;border:1px solid var(--line);border-radius:6px;
padding:6px 8px;color:#9fb0c8;font-size:12px;white-space:pre-wrap;margin:2px 0 8px}
.evt{color:#d9a520;font-size:12px}
.dth{color:var(--bad);font-size:12px}
.storm{color:#e07a2f;font-weight:bold}
#legend{font-size:11px;color:var(--dim);margin-top:8px}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;
vertical-align:-1px;margin:0 3px 0 10px}
</style></head><body><div id="wrap">
<h1 id="title"></h1><div class="sub" id="meta"></div>
<div id="ctrl"><button id="prev">&#9664;</button><button id="play">&#9654; play</button>
<button id="next">&#9654;</button>
<input type="range" id="scrub" min="0" max="0" value="0">
<span id="solt" style="min-width:90px;text-align:right"></span></div>
<div id="top"><div id="map"><div id="grid"></div><div id="legend">
<span class="sw" style="background:#2a2620"></span>ground
<span class="sw" style="background:#3a3530"></span>basalt
<span class="sw" style="background:#17435e"></span>ice
<span class="sw" style="background:#05060a"></span>crater
<span class="sw sbase"></span>base
<span class="sw spanel"></span>panel
<span class="sw sextractor"></span>extractor
<span class="sw sgreenhouse"></span>greenhouse
</div></div>
<div id="side">
<div class="panel"><div class="lbl">colony storage</div><div id="stor"></div>
<div id="wx"></div></div>
<div class="panel"><div class="lbl">actions this sol</div><div id="acts"></div>
<div id="evts"></div></div>
<div class="panel"><div class="lbl">raw model outputs</div><div id="raws"></div></div>
</div></div></div>
<script>
const D = __DATA__;
const TER = {".":"tt","b":"tb","i":"ti","c":"tc"};
const CAPS = {power:100,water:200,o2:200,food:200};
const GC = {power:"#e0a52f",water:"#3d9bd9",o2:"#4ea1ff",food:"#39a95c"};
const grid = document.getElementById("grid");
let cur = 0, timer = null;

function buildMap(){
  const w = D.ticks[0].state.grid.w, h = D.ticks[0].state.grid.h;
  grid.style.gridTemplateColumns = `repeat(${w},15px)`;
  grid.innerHTML = "";
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const c = document.createElement("div");
    c.className = "cell"; c.id = `c${x}_${y}`; grid.appendChild(c);}
}
function render(){
  const t = D.ticks[cur], st = t.state;
  document.getElementById("solt").textContent = "sol " + st.tick + "/" + (D.ticks.length-1);
  document.getElementById("scrub").value = cur;
  for(let y=0;y<st.grid.h;y++)for(let x=0;x<st.grid.w;x++){
    const el = document.getElementById(`c${x}_${y}`);
    el.className = "cell " + TER[st.grid.terrain[y][x]]; el.innerHTML = "";}
  st.structures.forEach(s=>{
    const el=document.getElementById(`c${s.x}_${s.y}`);
    el.insertAdjacentHTML("beforeend",`<div class="st s${s.type}"></div>`);});
  st.agents.forEach(a=>{
    const el=document.getElementById(`c${a.x}_${a.y}`);
    el.insertAdjacentHTML("beforeend",
      `<div class="ag${a.alive?"":" dead"}" style="background:${a.alive?"#e8ecf4":"#8a4045"}" title="${a.id} e:${a.energy} h:${a.health}"></div>`);});
  const s2 = [];
  for(const k of ["power","water","o2","food"]){
    const v = st.storage[k], p = Math.min(100, 100*v/CAPS[k]);
    s2.push(`<div class="gauge"><div class="grow"><span>${k}</span><span>${v}</span></div>
    <div class="bar"><div class="fill" style="width:${p}%;background:${GC[k]}"></div></div></div>`);}
  document.getElementById("stor").innerHTML = s2.join("");
  document.getElementById("wx").innerHTML = st.weather.storm_ticks_left>0
    ? `<div class="storm">DUST STORM — ${st.weather.storm_ticks_left} sols left</div>`
    : `<span class="sub">weather: clear</span>`;
  document.getElementById("acts").innerHTML = t.actions.map(a=>
    `<div class="act"><b>${a.agent}</b> <span class="${a.status}">${a.status==="ok"?"OK":"REJECTED: "+a.reason}</span> ${JSON.stringify(a.action)}</div>`
  ).join("") || '<div class="sub">—</div>';
  let ev = t.events.map(e=>`<div class="evt">⚠ ${e.type}${e.duration?` (${e.duration} sols)`:""}</div>`).join("");
  ev += t.deaths.map(d=>`<div class="dth">☠ ${d.agent} died — ${d.cause}</div>`).join("");
  if(st.episode_over) ev += `<div class="dth">EPISODE OVER — ${st.episode_over.cause}</div>`;
  document.getElementById("evts").innerHTML = ev;
  const raws = (D.raws||[]).filter(r=>r.sol===t.tick);
  document.getElementById("raws").innerHTML = raws.length
    ? raws.map(r=>`<div class="sub">${r.agent} → ${JSON.stringify(r.parsed)}</div><div class="raw">${(r.raw||"").trim()||"(empty)"}</div>`).join("")
    : '<div class="sub">no raw outputs (scripted run?)</div>';
}
function go(n){ cur = Math.max(0, Math.min(D.ticks.length-1, n)); render(); }
document.getElementById("scrub").max = D.ticks.length-1;
document.getElementById("scrub").oninput = e=>go(+e.target.value);
document.getElementById("prev").onclick = ()=>go(cur-1);
document.getElementById("next").onclick = ()=>go(cur+1);
document.getElementById("play").onclick = e=>{
  if(timer){clearInterval(timer);timer=null;e.target.innerHTML="&#9654; play";}
  else{timer=setInterval(()=>go(cur>=D.ticks.length-1?(clearInterval(timer),timer=null,e.target.innerHTML="&#9654; play",0):cur+1),450);e.target.innerHTML="&#10074;&#10074; pause";}};
buildMap(); render();
</script></body></html>"""


def _llm_candidates(trace_path: str):
    base = trace_path
    if base.endswith(".trace.jsonl"):
        yield base[:-len(".trace.jsonl")] + ".llm.jsonl"
    yield base + ".llm.jsonl"


def build_html(trace_path: str, out_path=None, llm_path=None):
    """Embed a trace (+ optional raw-LLM sidecar) into a standalone HTML."""
    meta, ticks = None, []
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["kind"] == "run":
                meta = rec
            elif rec["kind"] == "tick":
                st = rec["state"]
                ticks.append({
                    "tick": rec["tick"],
                    "actions": rec["actions"],
                    "events": rec["events"],
                    "deaths": rec["deaths"],
                    "state": {"tick": st["tick"], "grid": st["grid"],
                              "storage": st["storage"],
                              "structures": st["structures"],
                              "agents": st["agents"],
                              "weather": st["weather"],
                              "episode_over": st["episode_over"]},
                })
    raws = []
    if llm_path is None:
        llm_path = next((p for p in _llm_candidates(trace_path)
                         if os.path.exists(p)), None)
    if llm_path and os.path.exists(llm_path):
        with open(llm_path, encoding="utf-8") as f:
            raws = [json.loads(l) for l in f]

    data = {"meta": meta, "ticks": ticks, "raws": raws}
    html = TEMPLATE.replace("__DATA__", json.dumps(data, sort_keys=True))
    extra = ""
    if len(html.encode()) > 8_000_000:
        extra = " (large episode — file will be big)"
    html = html.replace("</title>",
                        f" — {os.path.basename(trace_path)}{extra}</title>")
    out_path = out_path or (os.path.splitext(trace_path)[0] + ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path, len(ticks), bool(raws)

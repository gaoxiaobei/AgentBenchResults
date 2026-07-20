#!/usr/bin/env python3
"""Build static HTML report site from agentbench data.

Usage: python scripts/report_builder.py --data-dir ./ --output ./_site
"""

import argparse, json, sys, tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import jinja2
except ImportError:
    jinja2 = None

# =============================================================================
# Data model
# =============================================================================

@dataclass
class RunData:
    run_id: str; game: str; agent: str; type: str; path: str
    created: str = ""; git_commit: str = ""
    metrics: dict = field(default_factory=dict)
    raw_summary: dict = field(default_factory=dict)
    raw_metadata: dict = field(default_factory=dict)

    @property
    def best_elo(self) -> float|None: return self.metrics.get("best_elo")
    @property
    def final_elo(self) -> float|None: return self.metrics.get("final_elo")
    @property
    def wall_hours(self) -> float|None: return self.metrics.get("wall_hours")
    @property
    def total_steps(self) -> int|None: return self.metrics.get("total_steps")
    @property
    def win_rate(self) -> float|None: return self.metrics.get("win_rate")
    @property
    def elo_history(self) -> list: return self.raw_summary.get("elo_history", [])
    @property
    def h2h(self) -> dict: return self.raw_summary.get("h2h", {})

@dataclass
class GameData:
    name: str
    agents: list = field(default_factory=list)
    runs: list = field(default_factory=list)

# =============================================================================
# Data loading
# =============================================================================

def load_registry(data_dir: Path) -> list:
    p = data_dir / "registry.toml"
    if not p.exists(): return []
    return tomllib.loads(p.read_text()).get("runs", [])

def load_run(data_dir: Path, entry: dict) -> RunData:
    rp = data_dir / entry["path"]
    rs, rm = {}, {}
    sj = rp / "summary.json"
    if sj.exists():
        try: rs = json.loads(sj.read_text())
        except Exception: pass
    rt = rp / "run.toml"
    if rt.exists():
        try: rm = tomllib.loads(rt.read_text())
        except Exception: pass
    return RunData(
        run_id=entry["run_id"], game=entry["game"], agent=entry["agent"],
        type=entry.get("type","eval"), path=entry["path"],
        created=entry.get("created",""), git_commit=entry.get("git_commit",""),
        metrics=entry.get("summary",{}), raw_summary=rs, raw_metadata=rm,
    )

def load_compare(data_dir: Path) -> dict:
    p = data_dir / "reports" / "compare.toml"
    return tomllib.loads(p.read_text()) if p.exists() else {}

def group_by_game(runs: list) -> dict[str, GameData]:
    gs: dict = {}
    for r in runs:
        if r.game not in gs: gs[r.game] = GameData(name=r.game)
        gd = gs[r.game]
        if r.agent not in gd.agents: gd.agents.append(r.agent)
        gd.runs.append(r)
    return gs

# =============================================================================
# Helpers
# =============================================================================

def _fmt_num(v, prec=1):
    if v is None: return "-"
    if isinstance(v, float): return f"{v:.{prec}f}"
    return str(v)

def _elo_color(elo):
    if elo is None: return "var(--text-dim)"
    if elo >= 1600: return "var(--success)"
    if elo >= 1400: return "var(--accent)"
    if elo >= 1200: return "var(--warning)"
    return "var(--danger)"

CHARTS_JS = r"""// AgentBench charts.js — Chart.js 4.x
(function(){'use strict';
var C=['#5B8DEF','#E8A838','#4ABF8A','#A078E8','#E85D75','#38B2C8','#F0A060','#78C870'];
function rc(i){return C[i%C.length]}
function ad(){return{grid:{color:'#252738'},ticks:{color:'#5D5F6D',font:{size:11}}}}
function td(){return{backgroundColor:'#1C1E2C',titleColor:'#E8E9ED',bodyColor:'#9698A5',borderColor:'#32354A',borderWidth:1,padding:12,cornerRadius:6}}
window.AgentBench=window.AgentBench||{};
window.AgentBench.lineChart=function(id,labels,datasets,extra){
  var ctx=document.getElementById(id).getContext('2d');
  var ds=datasets.map(function(d,i){var c=d.color||rc(i);return{label:d.label,data:d.data,borderColor:c,backgroundColor:c+'18',borderWidth:2,pointRadius:2,pointHoverRadius:5,tension:0.3,fill:false,spanGaps:true}});
  var opts={responsive:true,maintainAspectRatio:false,animation:{duration:400},plugins:{legend:{position:'bottom',labels:{color:'#9698A5',usePointStyle:true,padding:16,font:{size:12}}},tooltip:td()},scales:{x:ad(),y:ad()},interaction:{intersect:false,mode:'index'}};
  if(extra)Object.assign(opts,extra);new Chart(ctx,{type:'line',data:{labels:labels,datasets:ds},options:opts});
};
window.AgentBench.h2hHeatmap=function(id,labels,matrix){
  var container=document.getElementById(id);
  var canvas=document.createElement('canvas');container.appendChild(canvas);
  var n=labels.length,size=Math.min(600,container.clientWidth||400);
  canvas.width=size+60;canvas.height=size+60;
  var ctx=canvas.getContext('2d'),pad=50,cell=(size-pad)/n;
  ctx.fillStyle='#0D0E17';ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.font='11px -apple-system,sans-serif';ctx.fillStyle='#9698A5';ctx.textAlign='right';
  for(var i=0;i<n;i++){ctx.fillText(labels[i],pad-6,pad+i*cell+cell/2+4)}
  ctx.save();ctx.translate(pad,pad);
  for(var i=0;i<n;i++){ctx.save();ctx.translate(i*cell+cell/2,(n+0.3)*cell);ctx.rotate(-Math.PI/4);ctx.textAlign='right';ctx.fillStyle='#9698A5';ctx.fillText(labels[i],0,0);ctx.restore()}
  for(var i=0;i<n;i++){for(var j=0;j<n;j++){var v=matrix[i][j],r=Math.floor(v>=0.5?91+164*(v-0.5)*2:232-141*(0.5-v)*2),g=Math.floor(v>=0.5?141+50*(v-0.5)*2:168-27*(0.5-v)*2),b=Math.floor(v>=0.5?239-165*(v-0.5)*2:117-117*(0.5-v)*2);ctx.fillStyle='rgb('+r+','+g+','+b+')';ctx.fillRect(j*cell+1,i*cell+1,cell-2,cell-2);ctx.fillStyle='#E8E9ED';ctx.font='10px monospace';ctx.textAlign='center';ctx.fillText((v*100).toFixed(0)+'%',j*cell+cell/2,i*cell+cell/2+4)}}ctx.restore();
};
window.AgentBench.barChart=function(id,labels,datasets,extra){
  var ctx=document.getElementById(id).getContext('2d');
  var ds=datasets.map(function(d,i){var c=d.color||rc(i);return{label:d.label,data:d.data,backgroundColor:d.backgroundColor||c+'99',borderColor:c,borderWidth:1,borderRadius:4}});
  var opts={responsive:true,maintainAspectRatio:false,animation:{duration:400},plugins:{legend:{position:'bottom',labels:{color:'#9698A5',usePointStyle:true,padding:16,font:{size:12}}},tooltip:td()},scales:{x:ad(),y:ad()}};
  if(extra)Object.assign(opts,extra);new Chart(ctx,{type:'bar',data:{labels:labels,datasets:ds},options:opts});
};
window.AgentBench.scatterChart=function(id,datasets,extra){
  var ctx=document.getElementById(id).getContext('2d');
  var ds=datasets.map(function(d,i){var c=d.color||rc(i);return{label:d.label,data:d.data,backgroundColor:c+'99',borderColor:c,borderWidth:1,pointRadius:6,pointHoverRadius:8}});
  var opts={responsive:true,maintainAspectRatio:false,animation:{duration:400},plugins:{legend:{position:'bottom',labels:{color:'#9698A5',usePointStyle:true,padding:16}},tooltip:td()},scales:{x:ad(),y:ad()}};
  if(extra)Object.assign(opts,extra);new Chart(ctx,{type:'scatter',data:{datasets:ds},options:opts});
};
})();
"""

# =============================================================================
# Build
# =============================================================================

def build_site(data_dir, output, template_dir=None):
    if jinja2 is None:
        raise ImportError("jinja2 required: pip install jinja2")

    dp = Path(data_dir); op = Path(output)
    td = Path(template_dir) if template_dir else Path(__file__).resolve().parent / "templates"
    if not td.is_dir():
        print(f"Template dir not found: {td}", file=sys.stderr); return

    registry = load_registry(dp)
    runs = [load_run(dp, e) for e in registry]
    games = group_by_game(runs)
    compare = load_compare(dp)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(td)), autoescape=jinja2.select_autoescape(["html","xml"]))
    env.globals["fmt_num"] = _fmt_num
    env.globals["elo_color"] = _elo_color
    env.globals["tojson"] = lambda o: json.dumps(o, ensure_ascii=False)

    op.mkdir(parents=True, exist_ok=True)
    (op / "assets").mkdir(exist_ok=True)
    (op / "assets" / "charts.js").write_text(CHARTS_JS)

    gt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sr = sorted(runs, key=lambda r: r.created, reverse=True)

    def render(tpl, fname, depth=0, **kw):
        t = env.get_template(tpl)
        (op / fname).write_text(t.render(page=tpl.replace(".html",""), depth=depth,
            gen_time=gt, runs=sr, games=games, compare=compare, **kw))

    render("index.html", "index.html")
    for gn, gd in sorted(games.items()):
        gdir = op / gn; gdir.mkdir(exist_ok=True)
        render("game.html", f"{gn}/index.html", depth=1, game=gd, game_runs=gd.runs)
        for an in sorted(gd.agents):
            adir = gdir / an; adir.mkdir(exist_ok=True)
            ar = [r for r in gd.runs if r.agent == an]
            render("agent.html", f"{gn}/{an}/index.html", depth=2, game=gd, agent=an, agent_runs=sorted(ar, key=lambda r: r.created))
    render("compare.html", "compare.html")

    dj = {"runs": [{"run_id":r.run_id,"game":r.game,"agent":r.agent,"type":r.type,"created":r.created,"git_commit":r.git_commit,"metrics":r.metrics,"elo_history":r.elo_history,"h2h":r.h2h} for r in runs],
          "games": {n:{"agents":g.agents,"run_count":len(g.runs)} for n,g in games.items()},
          "compare": compare}
    (op / "data.json").write_text(json.dumps(dj, indent=2, ensure_ascii=False))
    print(f"Built: {len(runs)} runs, {len(games)} games -> {op}", file=sys.stderr)

def main():
    p = argparse.ArgumentParser(description="Build static HTML report site")
    p.add_argument("--data-dir", default="."); p.add_argument("--output", default="./_site")
    p.add_argument("--templates", default=None)
    args = p.parse_args()
    build_site(args.data_dir, args.output, args.templates)

if __name__ == "__main__":
    main()

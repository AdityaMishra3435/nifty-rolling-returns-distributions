"""
Builds output/dashboard.html: a single, self-contained interactive file.

The daily TRI series are embedded as data and every rolling return is computed
in the browser, so any combination of indices, holding periods (in monthly
steps) and start-date ranges can be explored without re-running Python.
Plotly is embedded from the installed `plotly` Python package, so the file
works offline. If that package is missing, it falls back to a CDN copy.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pandas as pd

EPOCH = pd.Timestamp("1970-01-01")
PLOTLY_CDN = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js"


def _plotly_js() -> tuple[str, str]:
    """Return (script_tag_html, description)."""
    try:
        import plotly  # noqa: WPS433
        p = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
        js = p.read_text(encoding="utf-8")
        return f"<script>{js}</script>", f"embedded (plotly {plotly.__version__})"
    except Exception:  # noqa: BLE001
        return f'<script src="{PLOTLY_CDN}"></script>', "CDN (needs internet to open)"


def build_dashboard(series: dict[str, pd.Series], path: Path, *, demo: bool,
                    generated: str, report_name: str = "report.html") -> tuple[Path, str]:
    payload = {"indices": {}, "demo": demo, "generated": generated}
    for name, s in series.items():
        days = ((s.index - EPOCH).days).astype(int).tolist()
        vals = [round(float(v), 4) for v in s.values]
        payload["indices"][name] = {"d": days, "v": vals}
    script_tag, plotly_desc = _plotly_js()
    html = (TEMPLATE
            .replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
            .replace("<!--__PLOTLY__-->", script_tag)
            .replace("__REPORT__", report_name)
            .replace("__DEMO_BANNER__", DEMO_BANNER if demo else ""))
    path.write_text(html, encoding="utf-8")
    return path, plotly_desc


DEMO_BANNER = ('<p class="demo">Demo mode: these series are randomly generated, not market '
               'data. They only show how the dashboard works. Run without <code>--demo</code> '
               'for real NSE data.</p>')

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nifty rolling returns by holding period</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#eef2f3; --surface:#ffffff; --ink:#18262e; --muted:#5a6b74; --line:#d5dde0;
  --accent:#1d5c7a; --neg:#b5473a; --chip:#e3eaed; --focus:#d98c1e;
  --sans:"Instrument Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --serif:"Newsreader", Georgia, "Times New Roman", serif;
}
@media (prefers-color-scheme: dark){
  :root{ color-scheme:dark; --paper:#0f171c; --surface:#16222a; --ink:#e4ecef; --muted:#93a4ad;
    --line:#2a3a43; --accent:#5fa8c9; --neg:#e07a6c; --chip:#203039; --focus:#e9a53f; }
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 var(--sans)}
header{padding:28px 32px 6px;max-width:1500px;margin:0 auto}
h1{font:600 clamp(26px,3.2vw,38px)/1.12 var(--serif);margin:0 0 6px;letter-spacing:-.01em;max-width:30ch}
.lede{color:var(--muted);margin:0;max-width:72ch}
.lede a{color:var(--accent)}
.demo{background:#fff3d6;color:#5b4310;border:1px solid #e8c46a;border-radius:6px;padding:8px 12px;margin:12px 0 0;max-width:80ch}
@media (prefers-color-scheme: dark){.demo{background:#2c2616;color:#f0d9a0;border-color:#8a7334}}
.app{display:grid;grid-template-columns:300px minmax(0,1fr);gap:22px;padding:18px 32px 40px;max-width:1500px;margin:0 auto}
aside{position:sticky;top:12px;align-self:start;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px 16px 6px}
fieldset{border:0;margin:0 0 18px;padding:0}
legend{font-weight:600;font-size:13.5px;margin-bottom:8px;padding:0}
.hint{color:var(--muted);font-size:12.5px;margin:6px 0 0}
.idx{display:flex;align-items:center;gap:9px;padding:5px 6px;border-radius:6px;cursor:pointer;font-size:14px}
.idx:hover{background:var(--chip)}
.idx input{accent-color:var(--accent);width:16px;height:16px;margin:0}
.sw{width:12px;height:12px;border-radius:3px;flex:none}
.idx .nm{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.idx small{color:var(--muted);margin-left:auto;font-size:11.5px;font-variant-numeric:tabular-nums;white-space:nowrap}
.row2{display:grid;grid-template-columns:1fr auto 1fr;gap:6px;align-items:center}
.row2 span{color:var(--muted);font-size:13px}
input[type=number],select{width:100%;font:inherit;font-size:14px;color:var(--ink);background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:6px 8px}
.check{display:flex;gap:9px;align-items:flex-start;font-size:14px;cursor:pointer}
.check input{accent-color:var(--accent);margin-top:3px}
main{min-width:0}
.tabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin-bottom:12px}
.tab{font:500 14.5px var(--sans);color:var(--muted);background:none;border:0;border-bottom:2.5px solid transparent;padding:9px 14px 10px;cursor:pointer;margin-bottom:-1px}
.tab[aria-selected=true]{color:var(--ink);border-bottom-color:var(--accent)}
.tab:hover{color:var(--ink)}
button:focus-visible,input:focus-visible,select:focus-visible,.idx:focus-within{outline:2.5px solid var(--focus);outline-offset:2px}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px 10px}
.viewbar:empty{display:none}
.viewbar{display:flex;flex-wrap:wrap;gap:12px 18px;align-items:center;min-height:34px;margin-bottom:4px}
.viewbar label{font-size:13.5px;color:var(--muted);display:flex;gap:8px;align-items:center}
.viewbar select{width:auto}
.caption{color:var(--muted);font-size:13.5px;margin:2px 0 0;max-width:90ch}
#chart{width:100%;height:min(600px,66vh);min-height:420px}
.play{font:600 14px var(--sans);color:#fff;background:var(--accent);border:0;border-radius:6px;padding:7px 16px;cursor:pointer;min-width:84px}
.slider{flex:1;min-width:220px;display:flex;gap:10px;align-items:center}
.slider input{flex:1;accent-color:var(--accent)}
.hval{font:600 20px var(--serif);min-width:5.5ch;font-variant-numeric:tabular-nums}
.readout{display:flex;flex-wrap:wrap;gap:8px 26px;margin:6px 0 2px;font-size:13.5px}
.readout b{font-variant-numeric:tabular-nums}
h2{font:600 19px var(--serif);margin:26px 0 8px}
.tablewrap{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:7px 10px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);background:var(--surface)}
td:first-child,th:first-child,td:nth-child(2),th:nth-child(2){text-align:left}
tr.grp td{border-top:2px solid var(--line)}
td.thin{color:var(--muted)}
.neg{color:var(--neg)}
.empty{padding:60px 20px;text-align:center;color:var(--muted)}
footer{max-width:1500px;margin:0 auto;padding:0 32px 40px;color:var(--muted);font-size:12.5px}
footer p{max-width:100ch;margin:4px 0}
@media (max-width:860px){
  header{padding:20px 16px 4px}.app{grid-template-columns:1fr;padding:14px 16px 30px}
  aside{position:static}footer{padding:0 16px 30px}#chart{height:460px}
}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>
<!--__PLOTLY__-->
</head>
<body>
<header>
  <h1>How Nifty returns spread out as you hold longer</h1>
  <p class="lede">Every trading day is treated as a possible start date. For each holding period,
  the charts show the full range of annualised returns investors actually got. Data is the
  Total Return Index (dividends reinvested). The static summary is in <a href="__REPORT__">report.html</a>.</p>
  __DEMO_BANNER__
</header>

<div class="app">
<aside aria-label="Choose what to compare">
  <fieldset>
    <legend>Indices</legend>
    <div id="idxlist"></div>
    <p class="hint">Tick two to compare them side by side.</p>
  </fieldset>
  <fieldset>
    <legend>Holding period (years)</legend>
    <div class="row2"><input id="minY" type="number" min="0.5" max="30" step="0.5" value="1" aria-label="Shortest holding period">
    <span>to</span><input id="maxY" type="number" min="1" max="30" step="0.5" value="20" aria-label="Longest holding period"></div>
  </fieldset>
  <fieldset>
    <legend>Investments started</legend>
    <div class="row2"><select id="fromY" aria-label="Earliest start year"></select><span>to</span><select id="toY" aria-label="Latest start year"></select></div>
    <p class="hint">Only windows that began in these years are counted.</p>
  </fieldset>
  <fieldset>
    <label class="check"><input id="common" type="checkbox"> <span>Use the same dates for every ticked index</span></label>
    <p class="hint">Makes comparisons fair: each index is cut to the dates all of them share.</p>
  </fieldset>
</aside>

<main>
  <div class="tabs" role="tablist" aria-label="Chart type">
    <button class="tab" role="tab" data-view="funnel" aria-selected="true">Funnel</button>
    <button class="tab" role="tab" data-view="ridge" aria-selected="false">Ridgeline</button>
    <button class="tab" role="tab" data-view="heat" aria-selected="false">Heatmap</button>
    <button class="tab" role="tab" data-view="hist" aria-selected="false">Animated histogram</button>
  </div>
  <section class="panel" aria-live="polite">
    <div class="viewbar" id="viewbar"></div>
    <div id="chart" role="img" aria-label="Chart"></div>
    <p class="caption" id="caption"></p>
  </section>
  <h2>Numbers at key holding periods</h2>
  <div class="tablewrap"><table id="stats"></table></div>
</main>
</div>

<footer>
  <p>Windows overlap: consecutive start dates share almost all their days, so thousands of windows
  are not thousands of independent outcomes. “Independent periods” is the length of history divided by the holding
  period. Below 2, a distribution mostly reflects one or two market cycles; those are drawn dotted or greyed.</p>
  <p>Returns ignore fund costs and taxes. Values before an index’s launch date are back-calculated by NSE Indices.
  Past returns are not a forecast.</p>
  <p id="gen"></p>
</footer>

<script>
"use strict";
const DATA = /*__DATA__*/null;
const PALETTE = ["#1d5c7a","#d98c1e","#7a3b69","#5b7f3a","#b5473a","#2f8f8a","#8a6d3b","#4b5bb5","#c2577f","#3f6f5a"];
const NAMES = Object.keys(DATA.indices);
const COLOR = Object.fromEntries(NAMES.map((n,i)=>[n,PALETTE[i%PALETTE.length]]));
const state = {sel: NAMES.slice(0, Math.min(2, NAMES.length)), minY:1, maxY:20, fromY:null, toY:null,
               common:false, view:"funnel", heatIdx:null, histM:12, fixedX:true, playing:false};

/* ---------- calendar arithmetic (days since 1970-01-01, proleptic Gregorian) ---------- */
function daysFromCivil(y,m,d){ y -= m<=2 ? 1 : 0; const era=Math.floor(y/400), yoe=y-era*400;
  const doy=Math.floor((153*(m+(m>2?-3:9))+2)/5)+d-1, doe=yoe*365+Math.floor(yoe/4)-Math.floor(yoe/100)+doy;
  return era*146097+doe-719468; }
function civilFromDays(z){ z+=719468; const era=Math.floor(z/146097), doe=z-era*146097;
  const yoe=Math.floor((doe-Math.floor(doe/1460)+Math.floor(doe/36524)-Math.floor(doe/146096))/365);
  const doy=doe-(365*yoe+Math.floor(yoe/4)-Math.floor(yoe/100)), mp=Math.floor((5*doy+2)/153);
  const d=doy-Math.floor((153*mp+2)/5)+1, m=mp+(mp<10?3:-9); return [yoe+era*400+(m<=2?1:0), m, d]; }
const DIM=[31,28,31,30,31,30,31,31,30,31,30,31];
const dim=(y,m)=> m===2 && ((y%4===0 && y%100!==0) || y%400===0) ? 29 : DIM[m-1];
const yearOf = z => civilFromDays(z)[0];

/* ---------- prepare series ---------- */
const S = {};
for (const n of NAMES){ const raw=DATA.indices[n], len=raw.d.length;
  const o={d:Int32Array.from(raw.d), v:Float64Array.from(raw.v), y:new Int16Array(len), m:new Int8Array(len), dd:new Int8Array(len)};
  for(let i=0;i<len;i++){ const c=civilFromDays(o.d[i]); o.y[i]=c[0]; o.m[i]=c[1]; o.dd[i]=c[2]; }
  S[n]=o; }
const ALL_FIRST = Math.min(...NAMES.map(n=>S[n].d[0])), ALL_LAST = Math.max(...NAMES.map(n=>S[n].d[S[n].d.length-1]));

function lowerBound(arr, x){ let lo=0, hi=arr.length; while(lo<hi){ const mid=(lo+hi)>>1; if(arr[mid]<x) lo=mid+1; else hi=mid; } return lo; }
function clipBounds(name){ const s=S[name]; let a=s.d[0], b=s.d[s.d.length-1];
  if (state.common && state.sel.length>1){ for(const n of state.sel){ a=Math.max(a,S[n].d[0]); b=Math.min(b,S[n].d[S[n].d.length-1]); } }
  const lo=lowerBound(s.d,a), hi=lowerBound(s.d,b+1)-1; return [lo,hi]; }
function startFilter(){ const f = state.fromY ? daysFromCivil(state.fromY,1,1) : -1e9;
  const t = state.toY ? daysFromCivil(state.toY,12,31) : 1e9; return [f,t]; }

/* ---------- rolling returns for one index and one holding period (months) ---------- */
const CACHE = new Map();
function rolling(name, months){
  const [lo,hi]=clipBounds(name), [f,t]=startFilter(), key=`${name}|${months}|${lo}|${hi}|${f}|${t}`;
  if (CACHE.has(key)) return CACHE.get(key);
  const s=S[name], out=[]; let j=lo, first=null, last=null;
  if (hi>lo){
    for (let i=lo;i<=hi;i++){
      const mAbs = s.m[i]-1-months, yy = s.y[i]+Math.floor(mAbs/12), mm=((mAbs%12)+12)%12+1;
      const target = daysFromCivil(yy, mm, Math.min(s.dd[i], dim(yy,mm)));
      if (target < s.d[lo]) continue;
      while (j+1<=hi && s.d[j+1]<=target) j++;
      const sd=s.d[j]; if (sd<f || sd>t || j>=i) continue;
      out.push(Math.pow(s.v[i]/s.v[j], 365.25/(s.d[i]-sd)) - 1);
      if (first===null) first=sd; last=s.d[i];
    }
  }
  const x=Float64Array.from(out).sort(), n=x.length;
  const res={x, n, indep: n ? (last-first)/365.25/(months/12) : 0};
  if (CACHE.size>4000) CACHE.clear();
  CACHE.set(key,res); return res;
}
function q(x,p){ const n=x.length; if(!n) return NaN; const h=(n-1)*p, l=Math.floor(h), u=Math.min(l+1,n-1); return x[l]+(h-l)*(x[u]-x[l]); }
function share(x, pred){ let c=0; for(const v of x) if(pred(v)) c++; return x.length? c/x.length : NaN; }
function kde(x, grid){ // Silverman bandwidth on an evenly thinned sorted sample
  const n=x.length; if(n<2) return grid.map(()=>0);
  const step=Math.max(1,Math.floor(n/2500)), sm=[]; for(let i=0;i<n;i+=step) sm.push(x[i]);
  let mu=0; for(const v of sm) mu+=v; mu/=sm.length; let sd=0; for(const v of sm) sd+=(v-mu)**2; sd=Math.sqrt(sd/(sm.length-1));
  const iqr=q(x,.75)-q(x,.25), sc=iqr>0?Math.min(sd,iqr/1.349):sd, bw=Math.max(0.9*sc*Math.pow(sm.length,-0.2),1e-4);
  const k=1/(sm.length*bw*Math.sqrt(2*Math.PI));
  return grid.map(g=>{ let a=0; for(const v of sm){ const z=(g-v)/bw; if(z>-6&&z<6) a+=Math.exp(-0.5*z*z); } return a*k; });
}

/* ---------- helpers ---------- */
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const pct = (v,d=1) => Number.isFinite(v) ? (v*100).toFixed(d)+"%" : "–";
const yrs = m => (m%12===0) ? `${m/12}Y` : `${(m/12).toFixed(m%6===0?1:2)}Y`;
function rgba(hex,a){ const h=hex.replace("#",""); const r=parseInt(h.slice(0,2),16),g=parseInt(h.slice(2,4),16),b=parseInt(h.slice(4,6),16); return `rgba(${r},${g},${b},${a})`; }
function monthsRange(){ let a=Math.round(state.minY*12), b=Math.round(state.maxY*12); if(b<a) [a,b]=[b,a]; return [Math.max(1,a), Math.max(a,b)]; }
function baseLayout(extra){
  const ink=css("--ink"), muted=css("--muted"), line=css("--line");
  return Object.assign({paper_bgcolor:"rgba(0,0,0,0)", plot_bgcolor:"rgba(0,0,0,0)",
    font:{family:css("--sans"), color:ink, size:13}, margin:{l:64,r:24,t:34,b:56},
    hoverlabel:{font:{family:css("--sans")}},
    xaxis:{gridcolor:line, zerolinecolor:line, linecolor:line, tickcolor:line, color:muted},
    yaxis:{gridcolor:line, zerolinecolor:line, linecolor:line, tickcolor:line, color:muted},
    legend:{orientation:"h", x:0, y:1.01, yanchor:"bottom", font:{size:12.5}}}, extra||{});
}
const CONFIG={responsive:true, displaylogo:false, modeBarButtonsToRemove:["lasso2d","select2d","autoScale2d"]};
function setCaption(t){ document.getElementById("caption").textContent=t; }
function emptyState(msg){ Plotly.purge("chart"); document.getElementById("chart").innerHTML=`<div class="empty">${msg}</div>`; }

/* ---------- view: funnel ---------- */
function renderFunnel(){
  document.getElementById("viewbar").innerHTML="";
  const [a,b]=monthsRange(), traces=[];
  let any=false;
  for (const n of state.sel){
    const xs=[], p5=[], p25=[], p50=[], p75=[], p95=[], ind=[], cnt=[];
    for (let m=a;m<=b;m++){ const r=rolling(n,m); if(r.n<20) continue;
      xs.push(m/12); p5.push(q(r.x,.05)); p25.push(q(r.x,.25)); p50.push(q(r.x,.5)); p75.push(q(r.x,.75)); p95.push(q(r.x,.95)); ind.push(r.indep); cnt.push(r.n); }
    if (!xs.length) continue; any=true;
    const c=COLOR[n], rev=a=>a.slice().reverse();
    const multi=state.sel.length>1;
    if(!multi){
      traces.push({x:xs.concat(rev(xs)), y:p5.concat(rev(p95)), fill:"toself", fillcolor:rgba(c,.11), line:{width:0}, hoverinfo:"skip", showlegend:false, legendgroup:n, type:"scatter"});
    } else {
      for (const yv of [p5,p95]) traces.push({x:xs, y:yv, mode:"lines", line:{color:rgba(c,.75), width:1}, hoverinfo:"skip", showlegend:false, legendgroup:n, type:"scatter"});
    }
    traces.push({x:xs.concat(rev(xs)), y:p25.concat(rev(p75)), fill:"toself", fillcolor:rgba(c, multi?.20:.26), line:{width:0}, hoverinfo:"skip", showlegend:false, legendgroup:n, type:"scatter"});
    const solid=p50.map((v,i)=> ind[i]>=2 || (i+1<ind.length && ind[i+1]>=2) ? v : null);
    const dotted=p50.map((v,i)=> ind[i]<2 || (i>0 && ind[i-1]<2) ? v : null);
    const cd=xs.map((_,i)=>[pct(p5[i]),pct(p25[i]),pct(p75[i]),pct(p95[i]),cnt[i].toLocaleString(),ind[i].toFixed(1)]);
    const ht=`<b>${n}</b><br>Holding %{x:.2f} years<br>Median %{y:.1%}<br>Middle half %{customdata[1]} to %{customdata[2]}<br>90% of windows %{customdata[0]} to %{customdata[3]}<br>%{customdata[4]} windows, ≈%{customdata[5]} independent periods<extra></extra>`;
    traces.push({x:xs, y:solid, mode:"lines", line:{color:c,width:2.6}, name:n, legendgroup:n, customdata:cd, hovertemplate:ht, connectgaps:false, type:"scatter"});
    traces.push({x:xs, y:dotted, mode:"lines", line:{color:c,width:2.2,dash:"dot"}, name:n+" (thin data)", legendgroup:n, showlegend:false, customdata:cd, hovertemplate:ht, connectgaps:false, type:"scatter"});
  }
  if(!any) return emptyState("Not enough history for this selection. Tick an index, widen the start years or shorten the holding period.");
  Plotly.react("chart", traces, baseLayout({
    xaxis:Object.assign(baseLayout().xaxis,{title:{text:"Holding period (years)"}, dtick: (b-a)/12>12?2:1}),
    yaxis:Object.assign(baseLayout().yaxis,{title:{text:"Annualised return"}, tickformat:".0%"}),
    shapes:[{type:"line", xref:"paper", x0:0, x1:1, y0:0, y1:0, line:{color:css("--neg"),width:1,dash:"dot"}}],
    hovermode:"closest"}), CONFIG);
  setCaption(state.sel.length>1 ? "Thick line: median. Shaded band: middle half of outcomes (25th–75th percentile). Thin lines: the range holding 90% of outcomes (5th and 95th percentiles). Dotted: fewer than 2 independent periods of history." : "Line: median. Darker band: middle half of outcomes (25th–75th percentile). Lighter band: 90% of outcomes (5th–95th). Dotted line: fewer than 2 independent periods of history.");
}

/* ---------- view: ridgeline ---------- */
function ridgeHorizons(){ const [a,b]=monthsRange(), lo=a/12, hi=b/12;
  let list = (hi-lo<=11) ? Array.from({length:Math.floor(hi)-Math.ceil(lo)+1},(_,i)=>Math.ceil(lo)+i) : [1,2,3,4,5,7,10,12,15,20,25,30].filter(h=>h>=lo&&h<=hi);
  if (lo<1 && !list.includes(lo)) list.unshift(lo);
  return list.filter(h=>h>0).map(h=>Math.round(h*12)); }
function renderRidge(){
  document.getElementById("viewbar").innerHTML="";
  const H=ridgeHorizons(); if(!H.length) return emptyState("Choose a holding-period range of at least one year.");
  let lo=Infinity, hi=-Infinity;
  for(const n of state.sel){ const r=rolling(n,H[0]); if(r.n>20){ lo=Math.min(lo,q(r.x,.005)); hi=Math.max(hi,q(r.x,.995)); } }
  if(!Number.isFinite(lo)) return emptyState("Not enough history for this selection.");
  lo=Math.max(lo,-0.8); hi=Math.min(hi,2.0); const pad=(hi-lo)*0.04; lo-=pad; hi+=pad;
  const grid=Array.from({length:220},(_,i)=>lo+(hi-lo)*i/219), traces=[], ticks=[], labels=[], ann=[];
  const rows=H.length;
  const surface=css("--surface"), rowsTr=[];
  H.forEach((m,k)=>{
    const off=(rows-1-k); ticks.push(off); labels.push(yrs(m));
    let thinTxt=null; const under=[], over=[];
    state.sel.forEach((n,si)=>{
      const r=rolling(n,m); if(r.n<20) return;
      const d=kde(r.x,grid), mx=Math.max(...d); if(!(mx>0)) return;
      const sc=1.55/mx, c=COLOR[n];
      let i0=d.findIndex(v=>v>mx*0.004), i1=d.length-1-d.slice().reverse().findIndex(v=>v>mx*0.004);
      const gx=grid.slice(i0,i1+1), yv=d.slice(i0,i1+1).map(v=>off+v*sc);
      const px=[gx[0]].concat(gx,[gx[gx.length-1]]), py=[off].concat(yv,[off]);
      under.push({x:px, y:py, fill:"toself", fillcolor:surface, line:{width:0}, mode:"lines", hoverinfo:"skip", showlegend:false, type:"scatter"});
      over.push({x:px, y:py, fill:"toself", fillcolor:rgba(c, state.sel.length>1?.20:.34), line:{width:0}, mode:"lines", hoverinfo:"skip", showlegend:false, type:"scatter"});
      over.push({x:gx, y:yv, mode:"lines", line:{color:c,width:1.7}, hoverinfo:"skip", name:n, legendgroup:n, legendrank:si, showlegend:k===0, type:"scatter"});
      const med=q(r.x,.5), mi=Math.min(grid.length-1,Math.max(0,Math.round((med-lo)/(hi-lo)*(grid.length-1))));
      over.push({x:[med,med], y:[off, off+d[mi]*sc], mode:"lines", line:{color:c,width:2.4}, showlegend:false, legendgroup:n,
        hovertemplate:`<b>${n}</b>, ${yrs(m)}<br>Median ${pct(med)}<br>10th–90th pct ${pct(q(r.x,.1))} to ${pct(q(r.x,.9))}<br>Negative ${pct(share(r.x,v=>v<0))} of windows<br>≈${r.indep.toFixed(1)} independent periods<extra></extra>`, type:"scatter"});
      if (r.indep<2) thinTxt=`≈${r.indep.toFixed(1)} independent periods`;
    });
    rowsTr.push(under.concat(over));
    if (thinTxt) ann.push({x:1, xref:"paper", xanchor:"right", y:off+0.3, text:thinTxt, showarrow:false, font:{size:11,color:css("--muted")}});
  });
  // top rows first, so each lower row's opaque underlay hides what lies behind it
  rowsTr.forEach(tr=>traces.push(...tr));
  Plotly.react("chart", traces, baseLayout({
    xaxis:Object.assign(baseLayout().xaxis,{title:{text:"Annualised return"}, tickformat:".0%", range:[lo,hi]}),
    yaxis:Object.assign(baseLayout().yaxis,{tickvals:ticks, ticktext:labels, showgrid:false, zeroline:false, range:[-0.3, rows+0.9], title:{text:"Holding period"}}),
    shapes:[{type:"line", xref:"x", yref:"paper", x0:0, x1:0, y0:0, y1:1, line:{color:css("--neg"),width:1,dash:"dot"}}],
    annotations:ann, hovermode:"closest"}), CONFIG);
  setCaption("Each row is the distribution of returns for one holding period, shortest at the top. Curves are scaled to the same height so their shapes can be compared; width shows spread. The vertical tick marks the median. Hover a tick for the numbers.");
}

/* ---------- view: heatmap ---------- */
function renderHeat(){
  const vb=document.getElementById("viewbar");
  if(!state.sel.includes(state.heatIdx)) state.heatIdx=state.sel[0];
  vb.innerHTML = state.sel.length>1 ? `<label>Index shown <select id="heatSel">${state.sel.map(n=>`<option ${n===state.heatIdx?"selected":""}>${n}</option>`).join("")}</select></label>` : "";
  const hs=document.getElementById("heatSel"); if(hs) hs.onchange=e=>{state.heatIdx=e.target.value; render();};
  const n=state.heatIdx; if(!n) return emptyState("Tick an index to see its heatmap.");
  const [a,b]=monthsRange(), cols=[];
  for(let m=a;m<=b;m++){ const r=rolling(n,m); if(r.n>=20) cols.push([m,r]); }
  if(!cols.length) return emptyState("Not enough history for this selection.");
  let lo=q(cols[0][1].x,.01), hi=q(cols[0][1].x,.99); lo=Math.max(lo,-0.8); hi=Math.min(hi,2.0);
  const NB=110, bw=(hi-lo)/NB, yc=Array.from({length:NB},(_,i)=>lo+bw*(i+.5));
  const z=yc.map(()=>new Array(cols.length).fill(0)), cd=yc.map(()=>new Array(cols.length).fill(0));
  const med=[], p10=[], p90=[], xs=[];
  cols.forEach(([m,r],j)=>{ xs.push(m/12); const cnt=new Array(NB).fill(0);
    for(const v of r.x){ const k=Math.floor((v-lo)/bw); if(k>=0&&k<NB) cnt[k]++; }
    const mx=Math.max(...cnt)||1; for(let k=0;k<NB;k++){ z[k][j]=cnt[k]/mx; cd[k][j]=cnt[k]/r.n; }
    med.push(q(r.x,.5)); p10.push(q(r.x,.1)); p90.push(q(r.x,.9)); });
  const surf=css("--surface"), acc=css("--accent"), ink=css("--ink");
  const traces=[{type:"heatmap", x:xs, y:yc, z, customdata:cd, colorscale:[[0,surf],[0.08,rgba(acc.length===7?acc:"#1d5c7a",.18)],[0.5,rgba(acc.length===7?acc:"#1d5c7a",.6)],[1,acc]],
      showscale:false, hovertemplate:"Holding %{x:.2f} years<br>Return ≈ %{y:.1%}<br>%{customdata:.1%} of windows in this band<extra></extra>"},
    {x:xs,y:med,mode:"lines",line:{color:ink,width:2},name:"Median",type:"scatter",hovertemplate:"Median %{y:.1%}<extra></extra>"},
    {x:xs,y:p10,mode:"lines",line:{color:ink,width:1.2,dash:"dash"},name:"10th / 90th percentile",type:"scatter",hovertemplate:"10th pct %{y:.1%}<extra></extra>"},
    {x:xs,y:p90,mode:"lines",line:{color:ink,width:1.2,dash:"dash"},showlegend:false,type:"scatter",hovertemplate:"90th pct %{y:.1%}<extra></extra>"}];
  Plotly.react("chart", traces, baseLayout({
    xaxis:Object.assign(baseLayout().xaxis,{title:{text:"Holding period (years)"}, showgrid:false}),
    yaxis:Object.assign(baseLayout().yaxis,{title:{text:"Annualised return"}, tickformat:".0%", showgrid:false}),
    shapes:[{type:"line", xref:"paper", x0:0, x1:1, y0:0, y1:0, line:{color:css("--neg"),width:1,dash:"dot"}}],
    hovermode:"closest"}), CONFIG);
  setCaption(`${n}. Each column is one holding period; stronger colour means more common. Columns are shaded relative to their own most common return, so the shape stays visible even where outcomes are tightly bunched. Hover for the actual share of windows.`);
}

/* ---------- view: animated histogram ---------- */
let timer=null;
function stopPlay(){ if(timer){ clearInterval(timer); timer=null; } state.playing=false; const b=document.getElementById("playBtn"); if(b) b.textContent="Play"; }
function renderHist(){
  const vb=document.getElementById("viewbar"), [a,b]=monthsRange();
  state.histM=Math.min(Math.max(state.histM,a),b);
  if(!document.getElementById("hSlider")){
    vb.innerHTML=`<button class="play" id="playBtn" type="button">${state.playing?"Pause":"Play"}</button>
      <div class="slider"><input id="hSlider" type="range" aria-label="Holding period in months"><span class="hval" id="hVal"></span></div>
      <label><input type="checkbox" id="fixX" ${state.fixedX?"checked":""}> Keep x-axis fixed</label>`;
    document.getElementById("hSlider").oninput=e=>{ stopPlay(); state.histM=+e.target.value; drawHist(); };
    document.getElementById("fixX").onchange=e=>{ state.fixedX=e.target.checked; drawHist(); };
    document.getElementById("playBtn").onclick=()=>{
      if(state.playing) return stopPlay();
      const [a2,b2]=monthsRange(); if(state.histM>=b2) state.histM=a2;
      state.playing=true; document.getElementById("playBtn").textContent="Pause";
      timer=setInterval(()=>{ const [,bb]=monthsRange(); if(state.histM>=bb) return stopPlay(); state.histM++; drawHist(); }, 110);
    };
  }
  const sl=document.getElementById("hSlider"); sl.min=a; sl.max=b; sl.step=1; sl.value=state.histM;
  if(!document.getElementById("readout")) document.getElementById("caption").insertAdjacentHTML("beforebegin",'<div class="readout" id="readout"></div>');
  drawHist();
}
function drawHist(){
  const m=state.histM, [a]=monthsRange();
  document.getElementById("hVal").textContent= m%12===0 ? `${m/12} yr` : `${Math.floor(m/12)} yr ${m%12} mo`;
  document.getElementById("hSlider").value=m;
  let lo=Infinity, hi=-Infinity;
  const ref = state.fixedX ? a : m;
  for(const n of state.sel){ const r=rolling(n,ref); if(r.n>20){ lo=Math.min(lo,q(r.x,.005)); hi=Math.max(hi,q(r.x,.995)); } }
  if(!Number.isFinite(lo)){ for(const n of state.sel){ const r=rolling(n,m); if(r.n>20){ lo=Math.min(lo,q(r.x,.005)); hi=Math.max(hi,q(r.x,.995)); } } }
  if(!Number.isFinite(lo)) return emptyState("Not enough history at this holding period.");
  lo=Math.max(lo,-0.8); hi=Math.min(hi,2.0);
  let cl=Infinity, ch=-Infinity; for(const n of state.sel){ const r=rolling(n,m); if(r.n>20){ cl=Math.min(cl,q(r.x,.01)); ch=Math.max(ch,q(r.x,.99)); } }
  let ymax=0;
  const size = Math.max(0.0025, Number.isFinite(cl) ? (ch-cl)/40 : (hi-lo)/70), traces=[], shapes=[{type:"line", xref:"x", yref:"paper", x0:0, x1:0, y0:0, y1:1, line:{color:css("--neg"),width:1,dash:"dot"}}], rd=[];
  for(const n of state.sel){ const r=rolling(n,m), c=COLOR[n];
    if(r.n<20){ rd.push(`<span><b style="color:${c}">${n}</b>: not enough history</span>`); continue; }
    const b0=Math.floor(Math.min(lo, r.x[0])/size)*size, nb=Math.ceil((Math.max(hi, r.x[r.n-1])-b0)/size)+1, cnt=new Array(nb).fill(0);
    for(const v of r.x){ cnt[Math.min(nb-1, Math.max(0, Math.floor((v-b0)/size)))]++; }
    const bx=cnt.map((_,k)=>b0+size*(k+.5)), by=cnt.map(c2=>100*c2/r.n); ymax=Math.max(ymax, ...by);
    const bl=bx.map(x=>`${pct(x-size/2)} to ${pct(x+size/2)}`);
    traces.push({type:"bar", x:bx, y:by, width:size, name:n, customdata:bl, marker:{color:rgba(c,state.sel.length>1?.55:.75), line:{color:c,width:.6}},
      hovertemplate:`<b>${n}</b><br>%{customdata}<br>%{y:.1f}% of windows<extra></extra>`});
    const med=q(r.x,.5); shapes.push({type:"line", xref:"x", yref:"paper", x0:med, x1:med, y0:0, y1:0.97, line:{color:c,width:1.8,dash:"dash"}});
    rd.push(`<span><b style="color:${c}">${n}</b>: median <b>${pct(med)}</b>, 10th–90th pct <b>${pct(q(r.x,.1))}</b> to <b>${pct(q(r.x,.9))}</b>, negative <b class="${share(r.x,v=>v<0)>0?"neg":""}">${pct(share(r.x,v=>v<0))}</b>, ${r.n.toLocaleString()} windows, ≈${r.indep.toFixed(1)} independent periods</span>`);
  }
  document.getElementById("readout").innerHTML=rd.join("");
  if(!traces.length) return emptyState("Not enough history at this holding period.");
  if(!document.querySelector("#chart .plot-container")) document.getElementById("chart").innerHTML="";
  Plotly.react("chart", traces, baseLayout({barmode:"overlay", bargap:0.02,
    xaxis:Object.assign(baseLayout().xaxis,{title:{text:"Annualised return"}, tickformat:".0%", range: state.fixedX?[lo,hi]:undefined, autorange: !state.fixedX}),
    yaxis:Object.assign(baseLayout().yaxis,{title:{text:"% of windows"}, ticksuffix:"%", range:[0, ymax*1.08], autorange:false}), shapes, hovermode:"closest"}), CONFIG);
  setCaption("Press Play to sweep the holding period month by month and watch the spread narrow. Dashed vertical lines mark each index’s median. With the x-axis fixed, every frame uses the scale of the shortest holding period; bars get narrower as outcomes bunch together.");
}

/* ---------- stats table ---------- */
function renderStats(){
  const [a,b]=monthsRange(), H=[1,3,5,7,10,15,20,25,30].map(h=>h*12).filter(m=>m>=a&&m<=b);
  if(a<12 && !H.includes(a)) H.unshift(a);
  let h=`<thead><tr><th>Index</th><th>Holding</th><th>Windows</th><th>Independent periods</th><th>Median</th><th>10th pct</th><th>90th pct</th><th>Worst</th><th>Best</th><th>Negative</th><th>Above 12%</th></tr></thead><tbody>`;
  state.sel.forEach(n=>{ H.forEach((m,i)=>{ const r=rolling(n,m);
    if(r.n<20){ h+=`<tr class="${i===0?"grp":""}"><td>${i===0?`<span class="sw" style="display:inline-block;background:${COLOR[n]};margin-right:6px"></span>${n}`:""}</td><td>${yrs(m)}</td><td colspan="9" class="thin">not enough history</td></tr>`; return; }
    const thin=r.indep<2?"thin":"";
    h+=`<tr class="${i===0?"grp":""}"><td>${i===0?`<span class="sw" style="display:inline-block;background:${COLOR[n]};margin-right:6px"></span>${n}`:""}</td><td>${yrs(m)}</td>
      <td>${r.n.toLocaleString()}</td><td class="${thin}">${r.indep.toFixed(1)}</td><td class="${thin}"><b>${pct(q(r.x,.5))}</b></td><td class="${thin}">${pct(q(r.x,.1))}</td><td class="${thin}">${pct(q(r.x,.9))}</td>
      <td class="${r.x[0]<0?"neg":""}">${pct(r.x[0])}</td><td>${pct(r.x[r.n-1])}</td><td class="${share(r.x,v=>v<0)>0?"neg":""}">${pct(share(r.x,v=>v<0))}</td><td>${pct(share(r.x,v=>v>0.12))}</td></tr>`; }); });
  if(!state.sel.length) h+=`<tr><td colspan="11" class="thin">Tick at least one index.</td></tr>`;
  document.getElementById("stats").innerHTML=h+"</tbody>";
}

/* ---------- controls ---------- */
function buildControls(){
  const list=document.getElementById("idxlist");
  list.innerHTML=NAMES.map(n=>{ const s=S[n]; return `<label class="idx"><input type="checkbox" value="${n}" ${state.sel.includes(n)?"checked":""}>
    <span class="sw" style="background:${COLOR[n]}"></span><span class="nm" title="${n}">${n}</span><small>${yearOf(s.d[0])}–${yearOf(s.d[s.d.length-1])}</small></label>`; }).join("");
  list.querySelectorAll("input").forEach(cb=>cb.onchange=()=>{ state.sel=NAMES.filter(n=>list.querySelector(`input[value="${CSS.escape(n)}"]`).checked); schedule(); });
  const y0=yearOf(ALL_FIRST), y1=yearOf(ALL_LAST), opts=Array.from({length:y1-y0+1},(_,i)=>y0+i);
  const fy=document.getElementById("fromY"), ty=document.getElementById("toY");
  fy.innerHTML=opts.map(y=>`<option ${y===y0?"selected":""}>${y}</option>`).join(""); ty.innerHTML=opts.map(y=>`<option ${y===y1?"selected":""}>${y}</option>`).join("");
  fy.onchange=()=>{ state.fromY=+fy.value; if(state.toY && state.toY<state.fromY){ ty.value=fy.value; state.toY=state.fromY; } schedule(); };
  ty.onchange=()=>{ state.toY=+ty.value; if(state.fromY && state.fromY>state.toY){ fy.value=ty.value; state.fromY=state.toY; } schedule(); };
  const mn=document.getElementById("minY"), mx=document.getElementById("maxY");
  const onY=()=>{ const a=parseFloat(mn.value), b=parseFloat(mx.value); if(Number.isFinite(a)&&a>0) state.minY=a; if(Number.isFinite(b)&&b>0) state.maxY=b; schedule(); };
  mn.oninput=onY; mx.oninput=onY;
  document.getElementById("common").onchange=e=>{ state.common=e.target.checked; schedule(); };
  document.querySelectorAll(".tab").forEach(t=>t.onclick=()=>{ stopPlay(); state.view=t.dataset.view;
    document.querySelectorAll(".tab").forEach(x=>x.setAttribute("aria-selected", x===t?"true":"false"));
    document.getElementById("viewbar").innerHTML=""; const ro=document.getElementById("readout"); if(ro) ro.remove(); render(); });
  document.getElementById("gen").textContent=`Generated ${DATA.generated}.`;
}
let pending=null;
function schedule(){ clearTimeout(pending); pending=setTimeout(()=>{ stopPlay(); render(); }, 160); }
function render(){
  if(!state.sel.length){ emptyState("Tick at least one index on the left."); setCaption(""); renderStats(); return; }
  try{
    if(document.querySelector("#chart .empty")) document.getElementById("chart").innerHTML="";
    ({funnel:renderFunnel, ridge:renderRidge, heat:renderHeat, hist:renderHist})[state.view]();
  }catch(err){ console.error(err); emptyState("Something went wrong drawing this chart: "+err.message); }
  renderStats();
}
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
if (typeof Plotly === "undefined"){
  document.querySelector("main").innerHTML='<div class="panel empty">The charting library did not load. Re-run the script with <code>plotly</code> installed (pip install plotly), or open this file while online.</div>';
} else { buildControls(); render(); }
</script>
</body>
</html>
"""

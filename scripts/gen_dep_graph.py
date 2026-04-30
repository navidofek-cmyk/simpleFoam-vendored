#!/usr/bin/env python3
"""
Generate a static HTML dependency graph for simpleFoam_vendored.
Parses CMakeLists.txt for module structure and sources.cmake for file counts.
Output: docs/index.html  (D3.js force-directed graph)

Usage:
    python3 scripts/gen_dep_graph.py
    # then open docs/index.html in a browser
"""
import re
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "vendor")
SOURCES_CMAKE = os.path.join(VENDOR, "sources.cmake")
CMAKE = os.path.join(ROOT, "CMakeLists.txt")
OUT_DIR = os.path.join(ROOT, "docs")
OUT_HTML = os.path.join(OUT_DIR, "index.html")

# ── Module definitions ──────────────────────────────────────────────────────

MODULES = {
    "of_core":    {"label": "OpenFOAM core",         "filter": "/OpenFOAM/",    "color": "#4e79a7"},
    "of_os":      {"label": "OSspecific (POSIX)",     "filter": "/OSspecific/",  "color": "#4e79a7"},
    "of_pstream": {"label": "Pstream (MPI)",          "filter": "/Pstream/",     "color": "#4e79a7"},
    "of_ff":      {"label": "fileFormats",            "filter": "/fileFormats/", "color": "#59a14f"},
    "of_tri":     {"label": "triSurface",             "filter": "/triSurface/",  "color": "#59a14f"},
    "of_surf":    {"label": "surfMesh",               "filter": "/surfMesh/",    "color": "#59a14f"},
    "of_fv":      {"label": "finiteVolume",           "filter": "/finiteVolume/","color": "#f28e2b"},
    "of_mt":      {"label": "meshTools",              "filter": "/meshTools/",   "color": "#f28e2b"},
    "of_pp":      {"label": "physicalProperties",     "filter": "/physicalProperties/", "color": "#edc948"},
    "of_lag":     {"label": "lagrangian/basic",       "filter": "/lagrangian/",  "color": "#76b7b2"},
    "of_sam":     {"label": "sampling",               "filter": "/sampling/",    "color": "#76b7b2"},
    "of_mtm":     {"label": "MomentumTransport (base)","filter": "/momentumTransportModels/", "color": "#b07aa1"},
    "of_mti":     {"label": "MomentumTransport (inc.)","filter": "/MomentumTransportModels/incompressible/", "color": "#b07aa1"},
    "of_fvm":     {"label": "fvModels",               "filter": "/fvModels/",    "color": "#ff9da7"},
    "of_fvc":     {"label": "fvConstraints",          "filter": "/fvConstraints/","color": "#ff9da7"},
}

EDGES = [
    ("of_os",   "of_core"),
    ("of_pstream","of_core"),
    ("of_ff",   "of_core"),
    ("of_tri",  "of_core"), ("of_tri", "of_ff"),
    ("of_surf", "of_core"), ("of_surf", "of_ff"), ("of_surf", "of_tri"),
    ("of_fv",   "of_core"), ("of_fv",  "of_mt"),  ("of_fv",  "of_tri"),
    ("of_mt",   "of_core"), ("of_mt",  "of_fv"),  ("of_mt",  "of_surf"), ("of_mt", "of_ff"),
    ("of_pp",   "of_core"), ("of_pp",  "of_fv"),
    ("of_lag",  "of_core"), ("of_lag", "of_mt"),  ("of_lag", "of_fv"),
    ("of_sam",  "of_core"), ("of_sam", "of_fv"),  ("of_sam", "of_mt"),
    ("of_sam",  "of_surf"), ("of_sam", "of_lag"),
    ("of_mtm",  "of_core"), ("of_mtm", "of_fv"),  ("of_mtm", "of_mt"),  ("of_mtm", "of_pp"),
    ("of_mti",  "of_mtm"),
    ("of_fvm",  "of_core"), ("of_fvm", "of_fv"),  ("of_fvm", "of_mt"),  ("of_fvm", "of_sam"),
    ("of_fvc",  "of_core"), ("of_fvc", "of_fv"),  ("of_fvc", "of_mt"),
    ("simpleFoam", "of_fv"), ("simpleFoam", "of_mt"), ("simpleFoam", "of_pp"),
    ("simpleFoam", "of_mtm"), ("simpleFoam", "of_mti"),
    ("simpleFoam", "of_sam"), ("simpleFoam", "of_fvm"), ("simpleFoam", "of_fvc"),
]

# ── Count source files per module ───────────────────────────────────────────

def count_sources():
    if not os.path.exists(SOURCES_CMAKE):
        return {}
    with open(SOURCES_CMAKE) as f:
        lines = [l.strip() for l in f if "${VENDOR_DIR}" in l]
    counts = {}
    for mod, info in MODULES.items():
        filt = info["filter"]
        counts[mod] = sum(1 for l in lines if filt in l)
    return counts

# ── Build graph data ─────────────────────────────────────────────────────────

def build_graph():
    src_counts = count_sources()
    nodes = []
    for mod, info in MODULES.items():
        n = src_counts.get(mod, 0)
        nodes.append({
            "id": mod,
            "label": info["label"],
            "color": info["color"],
            "sources": n,
            "radius": max(12, min(40, 8 + n // 10)),
        })
    nodes.append({
        "id": "simpleFoam",
        "label": "simpleFoamExtracted",
        "color": "#e15759",
        "sources": 1,
        "radius": 22,
    })
    links = [{"source": s, "target": t} for s, t in EDGES]
    return {"nodes": nodes, "links": links}

# ── HTML template ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>simpleFoam_vendored — dependency graph</title>
<style>
  body { margin: 0; background: #1a1a2e; font-family: sans-serif; color: #eee; overflow: hidden; }
  h1 { text-align: center; padding: 14px 0 2px; font-size: 1.15rem; color: #aaa; font-weight: 300; margin: 0; }
  p.sub { text-align: center; font-size: 0.78rem; color: #555; margin: 0 0 4px; }
  svg { width: 100%; height: calc(100vh - 68px); cursor: grab; }
  svg:active { cursor: grabbing; }
  .link { stroke: #444; stroke-opacity: 0.5; }
  .link.highlighted { stroke: #fff; stroke-opacity: 1; stroke-width: 2.5px !important; }
  .link.dimmed { stroke-opacity: 0.08; }
  .node circle { stroke: #222; stroke-width: 1.5px; cursor: pointer; transition: opacity 0.15s; }
  .node.dimmed circle { opacity: 0.15; }
  .node.dimmed text { opacity: 0.1; }
  .node text { font-size: 11px; fill: #ddd; pointer-events: none; }
  .node .count { font-size: 9px; fill: #888; }
  .node.selected circle { stroke: #fff; stroke-width: 3px; }
  .tooltip {
    position: absolute; background: #16213e; border: 1px solid #556;
    padding: 10px 14px; border-radius: 8px; font-size: 12px; pointer-events: none;
    opacity: 0; transition: opacity 0.15s; max-width: 240px; line-height: 1.6;
  }
  .tooltip b { color: #7ecfff; }
  .tooltip .deps { margin-top: 6px; color: #aaa; font-size: 11px; }
  #hint { position: fixed; bottom: 12px; left: 50%; transform: translateX(-50%);
    font-size: 11px; color: #444; pointer-events: none; }
</style>
</head>
<body>
<h1>simpleFoam_vendored — module dependency graph</h1>
<p class="sub">Scroll to zoom · drag canvas to pan · click node to highlight · drag node to pin</p>
<div class="tooltip" id="tip"></div>
<svg id="graph"></svg>
<div id="hint">click anywhere to deselect</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
const data = GRAPH_DATA;

const svg = d3.select("#graph");
const W = window.innerWidth, H = window.innerHeight - 68;
svg.attr("viewBox", [0, 0, W, H]);

// ── zoom ────────────────────────────────────────────────────────────────────
const zoomLayer = svg.append("g");
svg.call(d3.zoom()
  .scaleExtent([0.15, 4])
  .on("zoom", e => zoomLayer.attr("transform", e.transform)));

// deselect on background click
svg.on("click", (e) => { if (e.target.tagName === "svg") clearSelection(); });

// ── simulation ──────────────────────────────────────────────────────────────
const sim = d3.forceSimulation(data.nodes)
  .force("link", d3.forceLink(data.links).id(d => d.id).distance(130))
  .force("charge", d3.forceManyBody().strength(-500))
  .force("center", d3.forceCenter(W/2, H/2))
  .force("collision", d3.forceCollide(d => d.radius + 12));

// ── links ───────────────────────────────────────────────────────────────────
const link = zoomLayer.append("g").selectAll("line")
  .data(data.links).join("line")
  .attr("class","link").attr("stroke-width", 1.5)
  .attr("marker-end", "url(#arrow)");

// arrowhead
svg.append("defs").append("marker")
  .attr("id","arrow").attr("viewBox","0 -4 8 8").attr("refX",8).attr("refY",0)
  .attr("markerWidth",6).attr("markerHeight",6).attr("orient","auto")
  .append("path").attr("d","M0,-4L8,0L0,4").attr("fill","#666");

// ── nodes ───────────────────────────────────────────────────────────────────
const nodeG = zoomLayer.append("g").selectAll("g")
  .data(data.nodes).join("g").attr("class","node")
  .call(d3.drag()
    .on("start", (e,d) => { if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
    .on("drag",  (e,d) => { d.fx=e.x; d.fy=e.y; })
    .on("end",   (e,d) => { if(!e.active) sim.alphaTarget(0); }));

nodeG.append("circle")
  .attr("r", d => d.radius)
  .attr("fill", d => d.color);

nodeG.append("text").attr("dy","0.35em").attr("text-anchor","middle")
  .text(d => d.id === "simpleFoam" ? "simpleFoam" : d.id.replace("of_",""));

nodeG.append("text").attr("class","count").attr("dy","1.6em").attr("text-anchor","middle")
  .text(d => d.sources > 0 ? d.sources+" .C" : "");

// ── tooltip + click ─────────────────────────────────────────────────────────
const tip = document.getElementById("tip");
let selected = null;

function neighbors(d) {
  const nbr = new Set([d.id]);
  data.links.forEach(l => {
    if (l.source.id === d.id) nbr.add(l.target.id);
    if (l.target.id === d.id) nbr.add(l.source.id);
  });
  return nbr;
}

function clearSelection() {
  selected = null;
  nodeG.classed("selected", false).classed("dimmed", false);
  link.classed("highlighted", false).classed("dimmed", false);
  tip.style.opacity = 0;
}

nodeG.on("click", (e, d) => {
  e.stopPropagation();
  if (selected === d.id) { clearSelection(); return; }
  selected = d.id;
  const nbr = neighbors(d);
  nodeG.classed("selected", n => n.id === d.id)
       .classed("dimmed",   n => !nbr.has(n.id));
  link.classed("highlighted", l => l.source.id === d.id || l.target.id === d.id)
      .classed("dimmed",      l => l.source.id !== d.id && l.target.id !== d.id);

  const deps = data.links.filter(l => l.source.id === d.id).map(l => l.target.id);
  const rdeps = data.links.filter(l => l.target.id === d.id).map(l => l.source.id);
  tip.innerHTML =
    `<b>${d.label}</b><br>` +
    `ID: <code>${d.id}</code><br>` +
    `Source files: <b>${d.sources}</b>` +
    (deps.length  ? `<div class="deps">▶ depends on: ${deps.join(", ")}</div>`  : "") +
    (rdeps.length ? `<div class="deps">◀ used by: ${rdeps.join(", ")}</div>` : "");
  tip.style.opacity = 1;
  tip.style.left = (e.pageX + 14) + "px";
  tip.style.top  = (e.pageY - 20) + "px";
})
.on("mousemove", e => {
  if (selected) {
    tip.style.left = (e.pageX + 14) + "px";
    tip.style.top  = (e.pageY - 20) + "px";
  }
});

// ── tick ─────────────────────────────────────────────────────────────────────
sim.on("tick", () => {
  link
    .attr("x1", d => d.source.x)
    .attr("y1", d => d.source.y)
    .attr("x2", d => { const dx=d.target.x-d.source.x, dy=d.target.y-d.source.y;
                       const l=Math.sqrt(dx*dx+dy*dy)||1; return d.target.x - dx/l*d.target.radius; })
    .attr("y2", d => { const dx=d.target.x-d.source.x, dy=d.target.y-d.source.y;
                       const l=Math.sqrt(dx*dx+dy*dy)||1; return d.target.y - dy/l*d.target.radius; });
  nodeG.attr("transform", d => `translate(${d.x},${d.y})`);
});
</script>
</body>
</html>
"""

def main():
    graph = build_graph()
    os.makedirs(OUT_DIR, exist_ok=True)
    html = HTML_TEMPLATE.replace("GRAPH_DATA", json.dumps(graph, indent=2))
    with open(OUT_HTML, "w") as f:
        f.write(html)
    total = sum(n["sources"] for n in graph["nodes"])
    print(f"Generated: {OUT_HTML}")
    print(f"Modules: {len(MODULES)}  |  Edges: {len(EDGES)}  |  Total .C tracked: {total}")


if __name__ == "__main__":
    main()

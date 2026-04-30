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
    "of_core": {
        "label": "OpenFOAM core", "filter": "/OpenFOAM/", "color": "#4e79a7",
        "theory": (
            "The foundation of all OpenFOAM solvers. Provides the mesh abstraction "
            "(<code>polyMesh</code>, <code>fvMesh</code>), geometric fields "
            "(<code>volScalarField</code>, <code>volVectorField</code>), "
            "I/O system, dictionary parsing, linear algebra solvers "
            "(GAMG, PCG, PBiCGStab, smoothSolvers), and the RunTime Selection "
            "Table mechanism that enables dynamic type registration."
        ),
        "keywords": ["polyMesh", "fvMesh", "GeometricField", "GAMG", "PCG", "dictionary", "RunTime Selection"],
    },
    "of_os": {
        "label": "OSspecific (POSIX)", "filter": "/OSspecific/", "color": "#4e79a7",
        "theory": (
            "OS abstraction layer for Linux/POSIX. Handles file I/O operations "
            "(<code>uncollatedFileOperation</code>, <code>masterUncollatedFileOperation</code>), "
            "signal handling (SIGSEGV, SIGFPE), CPU/clock timers, and the "
            "<code>printStack</code> backtrace mechanism. The file operation classes "
            "determine how parallel processes read and write case files."
        ),
        "keywords": ["fileOperation", "uncollated", "masterUncollated", "printStack", "POSIX"],
    },
    "of_pstream": {
        "label": "Pstream (MPI)", "filter": "/Pstream/", "color": "#4e79a7",
        "theory": (
            "MPI communication layer. Wraps <code>MPI_Send</code>/<code>MPI_Recv</code> "
            "and collective operations (broadcast, reduce, gather) behind the "
            "<code>Pstream</code> abstraction. Enables domain-decomposed parallel "
            "runs where each MPI rank holds a subdomain. "
            "<code>processorPolyPatch</code> boundaries exchange halo data each iteration."
        ),
        "keywords": ["MPI", "Pstream", "processorPatch", "halo exchange", "domain decomposition"],
    },
    "of_ff": {
        "label": "fileFormats", "filter": "/fileFormats/", "color": "#59a14f",
        "theory": (
            "Readers and writers for surface geometry formats: STL (ASCII/binary), "
            "NAS/Nastran, OBJ, VTK. The VTK writers use <code>vtkWriteOps</code> "
            "to produce legacy VTK format for post-processing in ParaView. "
            "STL ASCII parsing is implemented as a Flex lexer grammar."
        ),
        "keywords": ["STL", "VTK", "NAS", "OBJ", "vtkWriteOps", "Flex lexer"],
    },
    "of_tri": {
        "label": "triSurface", "filter": "/triSurface/", "color": "#59a14f",
        "theory": (
            "Triangulated surface representation (<code>triSurface</code>). "
            "Used for geometry operations: surface intersection, point projection, "
            "nearest-point queries. Essential for snappyHexMesh and distance-based "
            "boundary conditions. Reads STL, OBJ, GTS, VTK, NAS triangle meshes."
        ),
        "keywords": ["triSurface", "surface intersection", "point projection", "STL reader"],
    },
    "of_surf": {
        "label": "surfMesh", "filter": "/surfMesh/", "color": "#59a14f",
        "theory": (
            "Generic surface mesh with arbitrary polygonal faces (<code>MeshedSurface</code>, "
            "<code>UnsortedMeshedSurface</code>). Supports format converters for "
            "AC3D, GTS, NAS, OBJ, OFF, OFS, SMESH, STARCD, STL, TRI, VTK, WRL, X3D. "
            "Used by sampling and post-processing to define output surfaces."
        ),
        "keywords": ["MeshedSurface", "surfZone", "surface formats", "AC3D", "STARCD"],
    },
    "of_fv": {
        "label": "finiteVolume", "filter": "/finiteVolume/", "color": "#f28e2b",
        "theory": (
            "Core FV discretisation. Implements the discrete operators acting on "
            "<code>fvMesh</code>: divergence (<code>fvc::div</code>), gradient "
            "(<code>fvc::grad</code>), Laplacian (<code>fvc::laplacian</code>), "
            "time derivative (<code>fvc::ddt</code>). Provides all interpolation "
            "schemes (linear, upwind, limitedLinear, MUSCL…), boundary condition "
            "types, and the <code>fvMatrix</code> sparse linear system assembled "
            "per transport equation. Also contains the SIMPLE/PISO/PIMPLE control "
            "loops and the pressure-velocity coupling infrastructure."
        ),
        "keywords": ["fvc::div", "fvc::grad", "fvMatrix", "SIMPLE", "PISO", "GAMG", "interpolation schemes", "boundary conditions"],
    },
    "of_mt": {
        "label": "meshTools", "filter": "/meshTools/", "color": "#f28e2b",
        "theory": (
            "Higher-level mesh utilities built on top of <code>polyMesh</code>: "
            "octree-based point/cell/face searching (<code>indexedOctree</code>), "
            "mesh region decomposition, non-conformal patch handling, "
            "cell sets/face sets/point sets, edge mesh operations, "
            "wave propagation algorithms (<code>FaceCellWave</code>), "
            "and mesh-to-mesh interpolation (<code>meshToMesh</code>)."
        ),
        "keywords": ["indexedOctree", "FaceCellWave", "meshToMesh", "cellSet", "faceSet", "nonConformal"],
    },
    "of_pp": {
        "label": "physicalProperties", "filter": "/physicalProperties/", "color": "#edc948",
        "theory": (
            "Reads fluid physical properties from <code>physicalProperties</code> "
            "(formerly <code>transportProperties</code>). Provides the "
            "<code>viscosityModel</code> abstraction: Newtonian (constant ν), "
            "power-law, Carreau, Cross, HerschelBulkley for non-Newtonian fluids. "
            "simpleFoam reads kinematic viscosity ν from this dictionary."
        ),
        "keywords": ["viscosityModel", "Newtonian", "kinematic viscosity", "transportProperties"],
    },
    "of_lag": {
        "label": "lagrangian/basic", "filter": "/lagrangian/", "color": "#76b7b2",
        "theory": (
            "Base classes for Lagrangian (particle-tracking) simulations. "
            "<code>particle</code> stores position and tracks particles through "
            "the Eulerian mesh using barycentric coordinates. "
            "<code>Cloud&lt;ParticleType&gt;</code> manages the particle ensemble. "
            "Required by the <code>sampling</code> module for streamline and "
            "particle-based set sampling."
        ),
        "keywords": ["particle", "Cloud", "barycentric coordinates", "particle tracking", "Lagrangian"],
    },
    "of_sam": {
        "label": "sampling", "filter": "/sampling/", "color": "#76b7b2",
        "theory": (
            "Runtime data extraction for post-processing. "
            "<b>sampledSurfaces</b>: interpolate fields onto planes, iso-surfaces, "
            "patch surfaces. <b>sampledSets</b>: extract along lines, arcs, "
            "uniform grids, cell centres. <b>probes</b>: point values over time. "
            "Results written as VTK, raw CSV, gnuplot formats. "
            "Configured in <code>system/controlDict</code> under <code>functions</code>."
        ),
        "keywords": ["sampledSurface", "sampledSet", "probes", "iso-surface", "VTK output"],
    },
    "of_mtm": {
        "label": "MomentumTransport (base)", "filter": "/momentumTransportModels/", "color": "#b07aa1",
        "theory": (
            "Abstract base for turbulence modelling. Defines the interface for "
            "RANS, LES and laminar closures: effective viscosity "
            "<code>nuEff()</code>, turbulent kinetic energy <code>k()</code>, "
            "dissipation <code>epsilon()</code>/<code>omega()</code>, and the "
            "<code>correct()</code> method called each iteration. "
            "Generalised Newtonian viscosity models also reside here."
        ),
        "keywords": ["RANS", "LES", "nuEff", "turbulence closure", "correct()", "momentumTransportModel"],
    },
    "of_mti": {
        "label": "MomentumTransport (incompressible)", "filter": "/MomentumTransportModels/incompressible/", "color": "#b07aa1",
        "theory": (
            "Incompressible turbulence models (constant density ρ=1). "
            "<b>RANS</b>: k-ε (standard, RNG, realizable), k-ω SST, "
            "Spalart-Allmaras, Launder-Sharma k-ε, v²-f, k-kL-ω. "
            "<b>LES</b>: Smagorinsky, dynamic k-equation, WALE. "
            "<b>Laminar</b>: for Re &lt; Re_crit or DNS. "
            "simpleFoam uses this module to solve the closure equations "
            "for k, ε (or ω) after each momentum/pressure iteration."
        ),
        "keywords": ["k-epsilon", "k-omega SST", "Spalart-Allmaras", "Smagorinsky", "RANS", "LES", "incompressible"],
    },
    "of_fvm": {
        "label": "fvModels", "filter": "/fvModels/", "color": "#ff9da7",
        "theory": (
            "Source term injection into transport equations. Models add or modify "
            "terms in the <code>fvMatrix</code> via <code>addSup()</code>: "
            "<b>MRF</b> (moving reference frame — rotating machinery), "
            "<b>porosity</b> (Darcy-Forchheimer resistance), "
            "<b>explicitPorositySource</b>, <b>codedFvModel</b> (runtime C++). "
            "Also includes inter-region coupling and rotor-disk actuator model."
        ),
        "keywords": ["fvModel", "MRF", "porosity", "Darcy-Forchheimer", "source term", "addSup"],
    },
    "of_fvc": {
        "label": "fvConstraints", "filter": "/fvConstraints/", "color": "#ff9da7",
        "theory": (
            "Hard constraints applied after equation solution: "
            "<b>fixedValueConstraint</b> enforces Dirichlet values on selected cells, "
            "<b>meanVelocityForce</b> adjusts a body force to achieve a target "
            "mean velocity (channel flow), <b>limitMag</b>/<b>limitPressure</b> "
            "clip field magnitudes to physical bounds. "
            "Called via <code>fvConstraints.constrain(field)</code>."
        ),
        "keywords": ["fvConstraint", "fixedValue", "meanVelocityForce", "limitMag", "constrain"],
    },
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

def get_files_per_module():
    if not os.path.exists(SOURCES_CMAKE):
        return {}
    with open(SOURCES_CMAKE) as f:
        lines = [l.strip().rstrip(")").replace("${VENDOR_DIR}/", "")
                 for l in f if "${VENDOR_DIR}" in l]
    result = {}
    for mod, info in MODULES.items():
        filt = info["filter"]
        result[mod] = sorted(
            os.path.basename(l) for l in lines if filt in l
        )
    return result


def build_graph():
    src_counts = count_sources()
    files = get_files_per_module()
    nodes = []
    for mod, info in MODULES.items():
        n = src_counts.get(mod, 0)
        nodes.append({
            "id": mod,
            "label": info["label"],
            "color": info["color"],
            "sources": n,
            "files": files.get(mod, []),
            "radius": max(12, min(40, 8 + n // 10)),
            "theory": info.get("theory", ""),
            "keywords": info.get("keywords", []),
        })
    nodes.append({
        "id": "simpleFoam",
        "label": "simpleFoamExtracted",
        "color": "#e15759",
        "sources": 1,
        "files": ["simpleFoam.C"],
        "radius": 22,
        "theory": (
            "<b>simpleFoam</b> is a steady-state, incompressible, turbulent RANS solver "
            "based on the <b>SIMPLE</b> algorithm "
            "(Semi-Implicit Method for Pressure-Linked Equations, Patankar &amp; Spalding 1972).<br><br>"
            "<b>Governing equations:</b><br>"
            "∇·U = 0 &nbsp;&nbsp;<i>(continuity)</i><br>"
            "∇·(UU) − ∇·(ν<sub>eff</sub>∇U) = −∇p &nbsp;&nbsp;<i>(momentum)</i><br><br>"
            "<b>SIMPLE loop each iteration:</b><br>"
            "1. Solve momentum equation with explicit pressure gradient → U*<br>"
            "2. Assemble pressure equation from continuity constraint → solve for p<br>"
            "3. Correct velocity: U = U* − (∇p)/a<sub>p</sub><br>"
            "4. Solve turbulence equations (k, ε or ω)<br>"
            "5. Repeat until residuals &lt; tolerance<br><br>"
            "<b>Under-relaxation</b> (α&lt;1) stabilises the iteration: "
            "U<sup>n+1</sup> = αU* + (1−α)U<sup>n</sup>.<br><br>"
            "<b>Default schemes</b> (pitzDaily):<br>"
            "div(phi,U): linearUpwind · div(phi,k): upwind<br>"
            "laplacian: Gauss linear corrected<br>"
            "p solver: GAMG + GaussSeidel smoother"
        ),
        "keywords": ["SIMPLE", "RANS", "steady-state", "incompressible", "pressure-velocity coupling",
                     "under-relaxation", "linearUpwind", "GAMG"],
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
  /* sidebar */
  #sidebar {
    position: fixed; top: 0; right: -340px; width: 320px; height: 100vh;
    background: #16213e; border-left: 1px solid #334; padding: 16px;
    box-sizing: border-box; transition: right 0.25s ease;
    display: flex; flex-direction: column; z-index: 10;
  }
  #sidebar.open { right: 0; }
  #sidebar h2 { margin: 0 0 4px; font-size: 1rem; color: #7ecfff; }
  #sidebar .meta { font-size: 11px; color: #666; margin-bottom: 10px; }
  #sidebar input {
    width: 100%; box-sizing: border-box; padding: 6px 10px;
    background: #0f0f1a; border: 1px solid #334; border-radius: 6px;
    color: #ddd; font-size: 12px; margin-bottom: 8px;
  }
  #sidebar input:focus { outline: none; border-color: #7ecfff; }
  #file-list {
    flex: 1; overflow-y: auto; font-size: 11px; font-family: monospace;
    color: #aaa; line-height: 1.8;
  }
  #file-list span { display: block; padding: 1px 4px; border-radius: 3px; }
  #file-list span:hover { background: #223; color: #fff; }
  #sb-theory {
    font-size: 11.5px; color: #bbb; line-height: 1.65; margin-bottom: 10px;
    padding: 10px; background: #0f1a2e; border-radius: 6px; border-left: 3px solid #334;
  }
  #sb-theory b { color: #7ecfff; }
  #sb-theory code { color: #ffd; font-size: 10.5px; }
  #sb-keywords { margin-bottom: 8px; }
  #sb-keywords span {
    display: inline-block; background: #1a3050; color: #7ecfff;
    border-radius: 4px; padding: 2px 7px; font-size: 10px; margin: 2px 2px 0 0;
  }
  .tabs { display: flex; gap: 4px; margin-bottom: 8px; }
  .tab {
    flex: 1; padding: 5px; border: 1px solid #334; border-radius: 5px;
    background: none; color: #666; font-size: 11px; cursor: pointer;
  }
  .tab.active { background: #1a3050; color: #7ecfff; border-color: #7ecfff; }
  #close-btn {
    position: absolute; top: 10px; right: 12px; background: none;
    border: none; color: #555; font-size: 18px; cursor: pointer; line-height: 1;
  }
  #close-btn:hover { color: #fff; }
</style>
</head>
<body>
<h1>simpleFoam_vendored — module dependency graph</h1>
<p class="sub">Scroll to zoom · drag to pan · click node to explore · double-click to open file list</p>
<div class="tooltip" id="tip"></div>
<svg id="graph"></svg>
<div id="hint">click background to deselect</div>
<div id="sidebar">
  <button id="close-btn" onclick="closeSidebar()">✕</button>
  <h2 id="sb-title">Module</h2>
  <div class="meta" id="sb-meta"></div>
  <div class="tabs">
    <button class="tab active" id="tab-theory" onclick="switchTab('theory')">Theory</button>
    <button class="tab" id="tab-files" onclick="switchTab('files')">Source files</button>
  </div>
  <div id="panel-theory">
    <div id="sb-theory"></div>
    <div id="sb-keywords"></div>
  </div>
  <div id="panel-files" style="display:none; flex-direction:column; flex:1; overflow:hidden;">
    <input id="sb-search" type="text" placeholder="filter files…" oninput="filterFiles()">
    <div id="file-list"></div>
  </div>
</div>
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

// ── sidebar ───────────────────────────────────────────────────────────────────
let sbFiles = [];
let activeTab = "theory";

function switchTab(tab) {
  activeTab = tab;
  document.getElementById("panel-theory").style.display = tab === "theory" ? "block" : "none";
  document.getElementById("panel-files").style.display  = tab === "files"  ? "flex"  : "none";
  document.getElementById("tab-theory").classList.toggle("active", tab === "theory");
  document.getElementById("tab-files").classList.toggle("active",  tab === "files");
}

function openSidebar(d) {
  sbFiles = d.files || [];
  document.getElementById("sb-title").textContent = d.label;
  document.getElementById("sb-meta").textContent =
    `${d.id}  ·  ${d.sources} source file${d.sources !== 1 ? "s" : ""}`;
  document.getElementById("sb-theory").innerHTML = d.theory || "<i style='color:#555'>No description yet.</i>";
  document.getElementById("sb-keywords").innerHTML =
    (d.keywords || []).map(k => `<span>${k}</span>`).join("");
  document.getElementById("sb-search").value = "";
  renderFiles(sbFiles);
  switchTab("theory");
  document.getElementById("sidebar").classList.add("open");
}

function closeSidebar() {
  document.getElementById("sidebar").classList.remove("open");
}

function renderFiles(files) {
  document.getElementById("file-list").innerHTML =
    files.map(f => `<span>${f}</span>`).join("");
}

function filterFiles() {
  const q = document.getElementById("sb-search").value.toLowerCase();
  renderFiles(sbFiles.filter(f => f.toLowerCase().includes(q)));
}

// double-click opens sidebar
nodeG.on("dblclick", (e, d) => { e.stopPropagation(); openSidebar(d); });

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

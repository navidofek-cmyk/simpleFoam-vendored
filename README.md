# simpleFoam_vendored

Build **simpleFoam without OpenFOAM installed on the host**.  
Approach: vendor all required OF source files and compile them via CMake inside a clean Ubuntu container.

**[Interactive dependency graph →](https://navidofek-cmyk.github.io/simpleFoam-vendored/)**  
15 modules · 45 dependency edges · double-click any node for theory + source files

**[Theory →](THEORY.md)**  
SIMPLE algorithm · RANS turbulence models · FV discretisation · all modules explained

> **Enable GitHub Pages:** repo → Settings → Pages → Source: `Deploy from a branch` → Branch: `master` / folder: `/docs` → Save

---

## Status

| Step | Status | Notes |
|------|--------|-------|
| Solver sources | ✅ | `solver/` — simpleFoam.C + .H fragments |
| Dependency collector | ✅ | `collect_deps.sh` — 1271 .C files → `vendor/` |
| CMake build system | ✅ | per-module OBJECT libs, whole-archive RunTime registrations |
| Standalone build | ✅ | clean Ubuntu 22.04, no OF on host, 42 MB binary |
| Serial run | ✅ | pitzDaily: SIMPLE converged in 287 iterations |
| Parallel MPI run | ✅ | pitzDaily 4 cores: SIMPLE converged in 293 iterations (2.7× speedup) |
| airFoil2D | ✅ | Spalart-Allmaras: SIMPLE converged in 313 iterations |

---

## Quickstart

### 1. Clone

```bash
git clone https://github.com/navidofek-cmyk/simpleFoam-vendored.git
cd simpleFoam-vendored
```

### 2. Build base image (downloads OF-10, ~2–5 min)

```bash
docker build -f Dockerfile.base -t openfoam10-base .
```

### 3. Collect vendor sources (~3 min)

```bash
mkdir -p vendor
docker run --rm \
  -v "$(pwd)/vendor:/out" \
  -v "$(pwd)/solver:/work/solver" \
  -v "$(pwd)/scripts:/work/scripts" \
  openfoam10-base bash -lc \
  "source /opt/openfoam10/etc/bashrc && bash /work/scripts/collect_deps.sh"
```

### 4. Build standalone solver (~15 min)

```bash
docker build -f Dockerfile.build -t simplefoam-vendored-build .
```

Result: `simpleFoamExtracted` binary inside the Docker image.

### 5. Extract binary

```bash
docker create --name tmp simplefoam-vendored-build
docker cp tmp:/build/build/simpleFoamExtracted ./simpleFoamExtracted
docker rm tmp
```

### 6. Run a test case (pitzDaily)

```bash
# Serial
docker build -f Dockerfile.test -t simplefoam-test .
# Output: SIMPLE solution converged in 287 iterations

# Parallel (4 cores)
docker build -f Dockerfile.test-parallel -t simplefoam-test-parallel .
# Output: SIMPLE solution converged in 293 iterations, ClockTime ~2s
```

---

## Repository structure

```
simpleFoam_vendored/
  solver/                  ← simpleFoam source (tracked in git)
  scripts/
    collect_deps.sh        ← collects OF deps, generates vendor/ + readSTLASCII.C
    run_collect.sh         ← helper to run collect_deps inside Docker
  vendor/                  ← generated (gitignored, ~48 MB)
    src/                   ← OF source files (1271 .C + headers)
    solver/                ← copy of solver sources
    sources.cmake          ← CMake source manifest
    preamble.H             ← standalone build preamble
  Dockerfile.base          ← OF-10 base image (for vendor collection)
  Dockerfile.build         ← standalone builder (ubuntu:22.04 + flex)
  CMakeLists.txt           ← build system
  chat_history/            ← development session transcripts
```

---

## Build architecture

### Why not wmake?

OpenFOAM normally compiles via `wmake` producing ~20 shared libraries (`.so`). The goal here is **one self-contained binary** with no runtime dependency on an installed OpenFOAM.

### Dependency graph

An interactive force-directed graph of all modules and their dependencies is available at:  
**https://navidofek-cmyk.github.io/simpleFoam-vendored/**

To regenerate locally:
```bash
python3 scripts/gen_dep_graph.py   # writes docs/index.html
```

### CMake module layout

Each OF module is a separate OBJECT library with the correct per-module include scope. They are merged into a single static library:

```
of_core  (OpenFOAM/)          ─┐
of_os    (OSspecific/)         │
of_pstream (Pstream/)          │
of_ff    (fileFormats/)        ├─► libopenfoam_vendor.a ─► simpleFoamExtracted
of_tri   (triSurface/)         │
of_surf  (surfMesh/)           │
of_fv    (finiteVolume/)       │
of_mt    (meshTools/)          │
of_lag   (lagrangian/basic/)   │
of_sam   (sampling/)           │
of_fvm   (fvModels/)           │
of_fvc   (fvConstraints/)     ─┘
```

### RunTime Selection Tables

OpenFOAM uses C++ static initializers to register types (turbulence models, file operations, function entries, etc.) in RunTime Selection Tables.  
In a static library, the linker skips object files with no external references, silently dropping all registrations.

Solutions used:
- `of_os` built as STATIC library + `--whole-archive` → registers `uncollated` file operation
- `libopenfoam_vendor.a` linked with `--whole-archive` → registers all RunTime types
- `--allow-multiple-definition` → silences identical template instantiations across TUs
- `add_dependencies(simpleFoamExtracted openfoam_vendor of_os)` → correct parallel build ordering

### Excluded sources

Files referencing unvendored dependencies are excluded from compilation. simpleFoam is an incompressible steady-state solver — thermophysical models, ensight output writers and particle samplers are not needed:

| Module | Excluded | Reason |
|--------|----------|--------|
| fvModels | heat sources, solidification, 6DoF | require `basicThermo`/`solidThermo` |
| fvConstraints | temperature limiters | require `basicThermo` |
| sampling | ensight writers, distance surfaces | require `ensightFile`, `fvMeshSubset` |

---

## License & attribution

The vendored sources in `vendor/` are derived from **[OpenFOAM-10](https://github.com/OpenFOAM/OpenFOAM-10)**,
developed and maintained by [OpenFOAM Foundation](https://openfoam.org),
distributed under the **GNU General Public License v3.0**.

This repository as a whole is therefore also licensed under **GPL v3**.  
See [LICENSE](LICENSE) for details.

---

### vendor/ is not in git

Contains thousands of copied OpenFOAM source files (~48 MB, ~6 700 files).  
Always regenerated fresh via `collect_deps.sh`.

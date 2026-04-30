# simpleFoam_vendored

[![Build & Test](https://github.com/navidofek-cmyk/simpleFoam-vendored/actions/workflows/build-and-test.yml/badge.svg)](https://github.com/navidofek-cmyk/simpleFoam-vendored/actions/workflows/build-and-test.yml)

Build **simpleFoam without OpenFOAM installed on the host**.  
All required OpenFOAM-10 sources are vendored into this repo and compiled via CMake inside a clean Ubuntu 22.04 container.

**[Dependency graph →](https://navidofek-cmyk.github.io/simpleFoam-vendored/)**  
**[Theory →](https://navidofek-cmyk.github.io/simpleFoam-vendored/theory.html)**  
**[Case setup guide →](https://navidofek-cmyk.github.io/simpleFoam-vendored/case-setup.html)**  
**[Troubleshooting →](https://navidofek-cmyk.github.io/simpleFoam-vendored/troubleshooting.html)**  
**[Residuals notebook →](notebooks/residuals_analysis.ipynb)**  
**[Pre-built image →](https://ghcr.io/navidofek-cmyk/simplefoam-vendored-build)**

> **Enable GitHub Pages:** repo → Settings → Pages → Branch: `master` / folder: `/docs` → Save

---

## Test results

| Case | Type | Result |
|------|------|--------|
| pitzDaily serial | smoke + regression + performance | ✅ converged 287 iter, ~6s |
| pitzDaily 4×MPI | smoke + performance | ✅ converged 293 iter, ~2s |
| airFoil2D (Spalart-Allmaras) | smoke + regression | ✅ converged 313 iter, ~5s |

---

## Quickstart

### Option A — use the pre-built image (fastest)

```bash
docker pull ghcr.io/navidofek-cmyk/simplefoam-vendored-build:latest
docker create --name tmp ghcr.io/navidofek-cmyk/simplefoam-vendored-build:latest
docker cp tmp:/build/build/simpleFoamExtracted ./simpleFoamExtracted
docker rm tmp
./simpleFoamExtracted --help
```

### Option B — build from source

#### 1. Clone

```bash
git clone https://github.com/navidofek-cmyk/simpleFoam-vendored.git
cd simpleFoam-vendored
```

#### 2. Build OF base image (downloads OF-10, ~5 min)

```bash
docker build -f Dockerfile.base -t openfoam10-base .
```

#### 3. Collect vendor sources (~3 min, only needed if you modify collect_deps.sh)

```bash
docker run --rm \
  -v "$(pwd)/vendor:/out" \
  -v "$(pwd)/solver:/work/solver" \
  -v "$(pwd)/scripts:/work/scripts" \
  openfoam10-base bash -lc \
  "source /opt/openfoam10/etc/bashrc && bash /work/scripts/collect_deps.sh"
```

> **Note:** vendor/ is already committed to this repo — skip step 3 unless you need to update the vendored sources.

#### 4. Build standalone solver (~15 min)

```bash
docker build -f Dockerfile.build -t simplefoam-vendored-build .
```

#### 5. Extract binary

```bash
docker create --name tmp simplefoam-vendored-build
docker cp tmp:/build/build/simpleFoamExtracted ./simpleFoamExtracted
docker rm tmp
ls -lh simpleFoamExtracted   # ~42 MB
```

---

## Run test cases

### pitzDaily — serial

```bash
docker build -f - -t test-serial . << 'EOF'
FROM openfoam10-base AS runner
COPY simpleFoamExtracted /usr/local/bin/simpleFoamExtracted
RUN cp -r /opt/openfoam10/tutorials/incompressible/simpleFoam/pitzDaily /case
WORKDIR /case
RUN sed -i '/functions/,/^}/d' system/controlDict
RUN bash -lc "source /opt/openfoam10/etc/bashrc && blockMesh && simpleFoamExtracted"
EOF
# Expected: SIMPLE solution converged in 287 iterations
```

### pitzDaily — parallel (4 cores)

```bash
docker build -f - -t test-parallel . << 'EOF'
FROM openfoam10-base AS runner
COPY simpleFoamExtracted /usr/local/bin/simpleFoamExtracted
RUN cp -r /opt/openfoam10/tutorials/incompressible/simpleFoam/pitzDaily /case
WORKDIR /case
RUN sed -i '/functions/,/^}/d' system/controlDict
RUN printf 'FoamFile\n{\n    version 2.0;\n    format ascii;\n    class dictionary;\n    location "system";\n    object decomposeParDict;\n}\nnumberOfSubdomains 4;\nmethod scotch;\n' > system/decomposeParDict
RUN bash -lc "source /opt/openfoam10/etc/bashrc && blockMesh && decomposePar && \
    mpirun -n 4 --allow-run-as-root simpleFoamExtracted -parallel"
EOF
# Expected: SIMPLE solution converged in 293 iterations, ClockTime ~2s
```

### airFoil2D

```bash
docker build -f - -t test-airfoil . << 'EOF'
FROM openfoam10-base AS runner
COPY simpleFoamExtracted /usr/local/bin/simpleFoamExtracted
RUN cp -r /opt/openfoam10/tutorials/incompressible/simpleFoam/airFoil2D /case
WORKDIR /case
RUN bash -lc "source /opt/openfoam10/etc/bashrc && simpleFoamExtracted"
EOF
# Expected: SIMPLE solution converged in 313 iterations
```

---

## CI/CD

GitHub Actions workflow runs automatically on every push that changes `CMakeLists.txt`, `Dockerfile.build`, `vendor/` or `solver/`.

**Two jobs:**

```
Job 1 — build (~35 min first run, ~2 min cached)
  → builds Dockerfile.base + Dockerfile.build
  → pushes images to ghcr.io with registry cache
  → tags with git SHA

Job 2 — test (~5 min, always fast)
  → pulls pre-built images from ghcr.io
  → runs 3 test cases
  → checks smoke + regression + performance
```

**Three test types:**

| Type | What it checks | Fails when |
|------|---------------|-----------|
| **Smoke** | solver converged at all | crash, FOAM FATAL ERROR |
| **Regression** | iteration count ±10% of reference | numerics changed unexpectedly |
| **Performance** | ClockTime within limit | solver became much slower |

Reference values: `tests/reference/*.ref`

**Monitor runs:**  
https://github.com/navidofek-cmyk/simpleFoam-vendored/actions

---

## Repository structure

```
simpleFoam_vendored/
  solver/                        ← simpleFoam sources (simpleFoam.C + .H)
  vendor/                        ← vendored OpenFOAM-10 sources (5965 files, 48 MB)
    src/                         ← OF source files
    sources.cmake                ← CMake source manifest (auto-generated)
    preamble.H                   ← standalone build preamble
    solver/                      ← copy of solver sources
  scripts/
    collect_deps.sh              ← collects OF deps, runs inside openfoam10-base
    run_collect.sh               ← helper to run collect_deps in Docker
    gen_dep_graph.py             ← generates docs/index.html + docs/theory.html
  tests/
    reference/
      pitzDaily.ref              ← regression reference (287 iter, 60s limit)
      airFoil2D.ref              ← regression reference (313 iter)
  docs/
    index.html                   ← interactive D3.js dependency graph
    theory.html                  ← solver & module theory page
  .github/
    workflows/
      build-and-test.yml         ← CI/CD pipeline
  Dockerfile.base                ← OF-10 base image (for vendor collection)
  Dockerfile.build               ← standalone builder (ubuntu:22.04 + flex)
  CMakeLists.txt                 ← CMake build system
  THEORY.md                      ← theory in Markdown
  README.md                      ← this file
```

---

## Build architecture

### Why not wmake?

OpenFOAM normally builds via `wmake` producing ~20 shared libraries (`.so`). The goal here is **one self-contained binary** with no runtime dependency on an installed OpenFOAM.

### CMake module layout

Each OF module compiles as a separate OBJECT library with the correct per-module include paths. All modules merge into a single static library:

```
of_core  (OpenFOAM/)            ─┐
of_os    (OSspecific/)           │
of_pstream (Pstream/)            │
of_ff    (fileFormats/)          │
of_tri   (triSurface/)           ├─► libopenfoam_vendor.a ─► simpleFoamExtracted
of_surf  (surfMesh/)             │
of_fv    (finiteVolume/)         │
of_mt    (meshTools/)            │
of_lag   (lagrangian/basic/)     │
of_sam   (sampling/)             │
of_mtm   (MomentumTransport)     │
of_mti   (MomentumTransport inc) │
of_fvm   (fvModels/)             │
of_fvc   (fvConstraints/)       ─┘
```

### Key linker flags

| Flag | Purpose |
|------|---------|
| `--whole-archive` on `of_os` + `openfoam_vendor` | Forces all RunTime registrations (turbulence models, file operations, function entries) to be included — linker would otherwise skip object files with no external references |
| `--allow-multiple-definition` | Silences identical template instantiations that appear in multiple translation units (e.g. `VectorSpace<>` static members) |
| `add_dependencies(simpleFoamExtracted openfoam_vendor of_os)` | Ensures correct build ordering in parallel CMake build |

### Excluded sources

Files referencing unvendored dependencies are excluded. simpleFoam is an incompressible steady-state solver — thermophysical models, ensight writers and particle samplers are not needed:

| Module | Excluded files | Reason |
|--------|---------------|--------|
| fvModels | heat sources, solidification, 6DoF, inter-region | require `basicThermo` / `solidThermo` |
| fvConstraints | temperature limiters | require `basicThermo` |
| sampling | ensight writers, distance surfaces | require `ensightFile`, `fvMeshSubset` |

### Overlapping filter paths (fixed)

Some source files matched multiple CMake module filters (double compilation → duplicate symbols):

| File | Matched filters | Fix |
|------|----------------|-----|
| `fvConstraint.C` | `/finiteVolume/` AND `/fvConstraints/` | excluded from `SRCS_FV` |
| `fvModel.C` | `/finiteVolume/` AND `/fvModels/` | excluded from `SRCS_FV` |
| `matchPoints.C` | `/OpenFOAM/` AND `/meshTools/` | excluded from `SRCS_MT` |

---

## Dependency graph & theory

Generate / update the static website:

```bash
python3 scripts/gen_dep_graph.py
# writes: docs/index.html  (interactive D3.js graph)
#         docs/theory.html (solver & module theory)
```

**Graph features:**
- Scroll to zoom, drag to pan
- Click node → highlight direct dependencies
- Double-click → sidebar with Theory tab + Source files tab + keyword tags

---

## License & attribution

The vendored sources in `vendor/` are derived from **[OpenFOAM-10](https://github.com/OpenFOAM/OpenFOAM-10)**,
developed and maintained by [OpenFOAM Foundation](https://openfoam.org),
distributed under the **GNU General Public License v3.0**.

This repository is therefore also licensed under **GPL v3**.  
See [LICENSE](LICENSE) for details.

# simpleFoam — Theory

This document covers the mathematical and algorithmic foundations behind simpleFoam and the OpenFOAM modules it depends on.

---

## simpleFoam — what is it?

**simpleFoam** is a steady-state, incompressible, turbulent RANS solver based on the **SIMPLE** algorithm (Semi-Implicit Method for Pressure-Linked Equations, Patankar & Spalding 1972).

It solves the Reynolds-Averaged Navier-Stokes (RANS) equations for incompressible flow:

```
∇·U = 0                                  (continuity)
∇·(UU) − ∇·(νeff ∇U) = −∇p              (momentum)
```

where `νeff = ν + νt` is the sum of molecular and turbulent kinematic viscosity.

### SIMPLE loop

Each iteration:

1. **Momentum predictor** — solve momentum with explicit pressure gradient → `U*`
2. **Pressure equation** — assemble from continuity constraint, solve for `p`
3. **Velocity corrector** — `U = U* − ∇p / aP`
4. **Turbulence equations** — solve for `k`, `ε` or `ω`
5. **Repeat** until all residuals < tolerance

### Under-relaxation

Stabilises the iteration:

```
U^(n+1) = α·U* + (1−α)·U^n        (α = 0.7 typical)
p^(n+1) = β·p* + (1−β)·p^n        (β = 0.3 typical)
```

### Default numerical schemes (pitzDaily)

| Term | Scheme |
|------|--------|
| `div(phi, U)` | linearUpwind |
| `div(phi, k)` | upwind |
| `div(phi, epsilon)` | upwind |
| `laplacian(nu, U)` | Gauss linear corrected |
| `p` solver | GAMG + GaussSeidel smoother |

---

## Module theory

### of_core — OpenFOAM core

Foundation of all OpenFOAM solvers. Provides:

- **Mesh abstraction** — `polyMesh`, `fvMesh`: cells, faces, points, boundary patches
- **Geometric fields** — `volScalarField`, `volVectorField`, `surfaceScalarField`
- **Linear solvers** — GAMG (algebraic multigrid), PCG, PBiCGStab, smoothSolvers
- **I/O system** — dictionary parsing, `IOobject`, `objectRegistry`
- **RunTime Selection** — dynamic type registration via static initializers

### of_pstream — MPI communication

Wraps MPI operations behind the `Pstream` abstraction:

- `MPI_Send`/`MPI_Recv` → point-to-point
- `MPI_Allreduce` → global reductions (sum, min, max)
- `processorPolyPatch` — boundary patches that exchange halo cell data each iteration

In a parallel run each MPI rank holds one subdomain. After solving locally, processor patches exchange ghost cell values before the next iteration.

### of_fv — Finite Volume discretisation

Implements discrete operators acting on `fvMesh`:

| Operator | Code | Discretisation |
|----------|------|----------------|
| Divergence | `fvc::div(phi, U)` | Gauss theorem: `∑_f φ_f U_f` |
| Gradient | `fvc::grad(p)` | Gauss: `∑_f p_f Sf` |
| Laplacian | `fvc::laplacian(nu, U)` | `∑_f ν_f |Sf|/|d| (U_N−U_P)` |
| Time deriv. | `fvc::ddt(U)` | Euler, backward, Crank-Nicolson |

`fvMatrix` assembles the sparse linear system `[A]{U} = {b}` per equation.

**Interpolation schemes** for face values: linear, upwind, linearUpwind, limitedLinear, MUSCL, vanLeer, QUICK, …

### of_mtm / of_mti — Turbulence models

RANS closure: replace Reynolds stress `−<u'u'>` with eddy viscosity hypothesis:

```
−<u'u'> = νt (∇U + ∇Uᵀ) − (2/3) k I
```

**Two-equation models (incompressible):**

| Model | Transport eqs. | Use case |
|-------|---------------|---------|
| k-ε standard | k, ε | general industrial |
| k-ε RNG | k, ε | swirl, separation |
| k-ω SST | k, ω | adverse pressure gradient, separation |
| Spalart-Allmaras | ν̃ | aerodynamics, airfoil |
| k-kL-ω | k, kL, ω | transitional flow |

**LES models** (large eddy simulation): Smagorinsky, dynamic k-equation, WALE — resolve large eddies, model small scales via SGS viscosity.

### of_mt — meshTools

Higher-level mesh operations:

- **`indexedOctree`** — O(log n) nearest-point / cell / face queries
- **`FaceCellWave`** — wave propagation for distance fields, region growing
- **`meshToMesh`** — field interpolation between non-matching meshes
- **Cell/face/point sets** — region selection for post-processing and BCs
- **Non-conformal patches** — AMI (Arbitrary Mesh Interface) for sliding meshes

### of_sam — Sampling

Runtime data extraction configured in `system/controlDict`:

- **sampledSurfaces** — interpolate fields onto planes (`cuttingPlane`), iso-surfaces, patch surfaces → VTK output
- **sampledSets** — extract along lines, arcs, uniform grids → CSV/gnuplot
- **probes** — point values written every N time steps
- **streamlines** — particle-tracked streamlines using Lagrangian integration

### of_lag — Lagrangian/basic

Base particle tracking library:

- **`particle`** — stores position as barycentric coordinates within a cell, tracks across faces using Lagrangian kinematics
- **`Cloud<ParticleType>`** — manages the ensemble, handles parallel transfer of particles across processor boundaries
- Used by `sampling` for streamline tracing and particle-based set sampling

### of_fvm — fvModels (source terms)

Inject additional terms into transport equations via `addSup()`:

- **MRF** (Moving Reference Frame) — rotating machinery without rotating mesh; adds Coriolis and centrifugal terms
- **Porosity / Darcy-Forchheimer** — `−(μ/K + C₂ρ|U|/2) U` resistance
- **codedFvModel** — runtime-compiled C++ source term
- **rotorDiskSource** — actuator disk model for propellers/fans

### of_fvc — fvConstraints

Hard constraints applied after equation solution:

- **fixedValueConstraint** — enforce Dirichlet value in selected cell zone
- **meanVelocityForce** — adjust body force to achieve target mean velocity (channel flow with periodic BCs)
- **limitMag** / **limitPressure** — clip field values to physical bounds

---

## Further reading

- Patankar, S.V. (1980). *Numerical Heat Transfer and Fluid Flow*. Taylor & Francis.
- Jasak, H. (1996). *Error Analysis and Estimation for the Finite Volume Method*. PhD thesis, Imperial College London.
- Versteeg, H.K. & Malalasekera, W. (2007). *An Introduction to CFD: The Finite Volume Method*. Pearson.
- OpenFOAM documentation: https://openfoam.org/documentation/

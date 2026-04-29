# simpleFoam_vendored

Cíl: zkompilovat **simpleFoam bez instalace OpenFOAM** na hostu.  
Přístup: vendorovat všechny OF zdrojáky které solver potřebuje a zkompilovat je přes CMake v čistém Ubuntu kontejneru.

---

## Stav projektu

| Krok | Stav | Poznámka |
|------|------|---------|
| Solver zdrojáky | ✅ | `solver/` — simpleFoam.C + .H fragmenty |
| Base Docker image | ✅ | `Dockerfile.base` — OF-10 na Ubuntu 22.04 |
| Sběr závislostí | ✅ | `collect_deps.sh` — 1271 .C souborů → `vendor/` |
| CMakeLists.txt | ✅ | per-module OBJECT libs, whole-archive RunTime registrations |
| Build (Dockerfile.build) | ✅ | čistý Ubuntu 22.04, bez OF na hostu |
| Solver běží (pitzDaily) | 🔄 in progress | RunTime registrace a functionEntries se debuggují |

---

## Quickstart (na novém počítači)

### 1. Naklonuj repo

```bash
git clone https://github.com/navidofek-cmyk/simpleFoam-vendored.git
cd simpleFoam-vendored
```

### 2. Postav base image (stáhne OF-10, ~2–5 min)

```bash
docker build -f Dockerfile.base -t openfoam10-base .
```

### 3. Vygeneruj vendor/ (sbírá zdrojáky z OF, ~3 min)

```bash
mkdir -p vendor
docker run --rm \
  -v "$(pwd)/vendor:/out" \
  -v "$(pwd)/solver:/work/solver" \
  -v "$(pwd)/scripts:/work/scripts" \
  openfoam10-base bash -lc \
  "source /opt/openfoam10/etc/bashrc && bash /work/scripts/collect_deps.sh"
```

### 4. Zkompiluj solver (čistý Ubuntu, bez OF, ~15 min)

```bash
docker build -f Dockerfile.build -t simplefoam-vendored-build .
```

Výsledek: binárka `simpleFoamExtracted` v Docker image.

### 5. Extrahuj binárku

```bash
docker create --name tmp simplefoam-vendored-build
docker cp tmp:/build/build/simpleFoamExtracted ./simpleFoamExtracted
docker rm tmp
```

---

## Struktura

```
simpleFoam_vendored/
  solver/                  ← simpleFoam.C + .H fragmenty (v gitu)
  scripts/
    collect_deps.sh        ← sbírá OF deps, generuje vendor/ + readSTLASCII.C
    run_collect.sh         ← helper pro spuštění v Dockeru
  vendor/                  ← generováno (není v gitu, ~48 MB)
    src/                   ← OF zdrojáky (1271 .C + hlavičky)
    solver/                ← kopie solveru
    sources.cmake          ← manifest zdrojáků pro CMake
    preamble.H             ← standalone build preamble
  Dockerfile.base          ← OF-10 base image (pro sběr deps)
  Dockerfile.build         ← standalone builder (ubuntu:22.04 + flex)
  CMakeLists.txt           ← build systém
  chat_history/            ← záznamy vývojových session
```

---

## Architektura buildu

### Proč ne wmake?

OpenFOAM normálně kompiluje přes `wmake` a generuje ~20 sdílených knihoven (`.so`). Cíl tohoto projektu je **jeden standalone binárka** bez závislosti na nainstalovaném OF.

### CMake přístup

Každý OF modul je samostatná `OBJECT library` se správnými include paths. Moduly se spojí do statické `libopenfoam_vendor.a`:

```
of_core (OpenFOAM/)     → of_fv (finiteVolume/)
of_os   (OSspecific/)   → of_mt (meshTools/)
of_lag  (lagrangian/)   → of_sam (sampling/)
...                     → simpleFoamExtracted
```

### RunTime Selection Tables

OF používá C++ static initializers pro registraci typů (turbulentní modely, file operations, atd.). Statická knihovna tyto initializers vynechá pokud na ně nic neodkazuje. Řešení:

- `--whole-archive` na `of_os` — zaregistruje `uncollated` file operation
- `--whole-archive` na `openfoam_vendor` — zaregistruje všechny RunTime typy

### Vyloučené soubory

Soubory referencující nevendorované deps jsou vyloučeny z kompilace. SimpleFoam je incompressible solver — thermophysical modely (`basicThermo`, `solidThermo`) a ensight output nejsou potřeba:

- `fvModels/`: thermophysical heat sources (buoyancy, heat transfer, solidification...)
- `fvConstraints/`: temperature constraints
- `sampling/`: ensight writers, distance surface (fvMeshSubset), particle samplers

---

## Proč vendor/ není v gitu

Obsahuje tisíce zkopírovaných souborů z OpenFOAM zdrojáků (~48 MB, ~6 700 souborů).  
Vždy se regeneruje čerstvě přes `collect_deps.sh`.

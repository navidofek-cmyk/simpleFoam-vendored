# simpleFoam_vendored

Cíl: zkompilovat simpleFoam **bez instalace OpenFOAM** na hostu.
Přístup: stáhnout všechny zdrojové soubory OF na které simpleFoam závisí,
zkompilovat je spolu se solverem přes CMake/Makefile.

---

## Stav projektu

| Krok | Stav | Poznámka |
|------|------|---------|
| 1. Solver zdrojáky | ✅ hotovo | `solver/` — simpleFoam.C + .H fragmenty |
| 2. Base Docker image | ✅ hotovo | `Dockerfile.base` — OF-10 na Ubuntu 22.04 |
| 3. Sběr závislostí (`collect_deps.sh`) | ✅ hotovo | 484 headerů, 267 .C souborů → `vendor/` |
| 4. Počet souborů | ✅ hotovo | **6 768 souborů, 48 MB** (vč. turbulentních modelů) |
| 5. CMakeLists.txt | ⏳ čeká | napíšeme podle výsledku kroku 3 |
| 6. Kompilace bez OF | ⏳ čeká | cíl: `cmake .. && make` |

---

## Struktura

```
simpleFoam_vendored/
  solver/              ← simpleFoam zdrojáky (v gitu)
    simpleFoam.C
    createFields.H
    UEqn.H
    pEqn.H
  scripts/
    collect_deps.sh    ← běží uvnitř OF kontejneru, sbírá deps
    run_collect.sh     ← spustí collect_deps.sh v Dockeru
  vendor/              ← vznikne po spuštění run_collect.sh (není v gitu)
    src/               ← zkopírované OF zdrojáky
    solver/            ← kopie solveru
  Dockerfile.base      ← OF-10 image pro sběr závislostí
  CMakeLists.txt       ← vznikne po kroku 3
```

---

## Jak spustit

### Krok 1 — sběr závislostí (první spuštění trvá déle, stahuje OF-10)

```bash
./scripts/run_collect.sh
```

Výsledek: `vendor/` naplněný OF zdrojáky.

### Krok 2 — kompilace (zatím nepřipraveno)

```bash
mkdir build && cd build
cmake ..
make -j$(nproc)
```

---

## Proč vendor/ není v gitu

Obsahuje tisíce souborů z OpenFOAM zdrojáků. Generuje se
vždy znovu přes `run_collect.sh`.

#!/usr/bin/env bash
# Runs inside a Docker container with OpenFOAM-10 installed.
# 1. Asks g++ for every header simpleFoam.C transitively includes.
# 2. For each OF header, copies it plus the matching .C implementation.
# 3. Recreates the lnInclude flat-include dirs so #include "Foo.H" still works.
# Output: /out/vendor/  (bind-mounted from host)
set -eo pipefail

OF_ROOT="${WM_PROJECT_DIR:-/opt/openfoam10}"
SOLVER_DIR="/work/solver"
OUT_DIR="/out/vendor"

# OF bashrc has internal commands that return non-zero — disable -eu around it
set +eu
# shellcheck disable=SC1091
source "${OF_ROOT}/etc/bashrc"
set -eu

SRC="${FOAM_SRC}"
echo "[1] Resolving header dependencies with g++ -MM ..."
echo "    FOAM_SRC=${SRC}"
INCLUDES=(
    -I"${SOLVER_DIR}"
    -I"${SRC}/OpenFOAM/lnInclude"
    -I"${SRC}/OSspecific/POSIX/lnInclude"
    -I"${SRC}/finiteVolume/lnInclude"
    -I"${SRC}/meshTools/lnInclude"
    -I"${SRC}/physicalProperties/lnInclude"
    -I"${SRC}/MomentumTransportModels/momentumTransportModels/lnInclude"
    -I"${SRC}/MomentumTransportModels/incompressible/lnInclude"
    -I"${SRC}/sampling/lnInclude"
    -I"${SRC}/fvModels/lnInclude"
    -I"${SRC}/fvConstraints/lnInclude"
    -I"${SRC}/finiteVolume/cfdTools/general/include"
    -DWM_DP -DWM_LABEL_SIZE=32
)

# g++ -MM gives us the full transitive header list
g++ -MM "${INCLUDES[@]}" "${SOLVER_DIR}/simpleFoam.C" 2>/dev/null \
    | tr ' \\' '\n' \
    | grep "^${OF_ROOT}" \
    | sort -u > /tmp/of_headers.txt

HEADER_COUNT=$(wc -l < /tmp/of_headers.txt)
echo "    Found ${HEADER_COUNT} OF headers."

echo "[2] Copying headers and matching .C implementation files ..."
mkdir -p "${OUT_DIR}"
COPIED_H=0
COPIED_C=0

while IFS= read -r hdr; do
    rel="${hdr#${SRC}/}"
    dst="${OUT_DIR}/src/${rel}"
    mkdir -p "$(dirname "${dst}")"
    cp -n "${hdr}" "${dst}" 2>/dev/null && (( COPIED_H++ )) || true

    # Matching implementation: same path, .H -> .C
    impl="${hdr%.H}.C"
    if [[ -f "${impl}" ]]; then
        dst_c="${OUT_DIR}/src/${impl#${SRC}/}"
        mkdir -p "$(dirname "${dst_c}")"
        cp -n "${impl}" "${dst_c}" 2>/dev/null && (( COPIED_C++ )) || true
    fi
done < /tmp/of_headers.txt

echo "    Headers copied : ${COPIED_H}"
echo "    .C files copied: ${COPIED_C}"

echo "[3] Recreating lnInclude flat dirs ..."
# Each module's lnInclude contains symlinks like Foo.H -> ../subdir/Foo.H
# We copy them as real files so CMake can use -I<module>/lnInclude
find "${OF_ROOT}/src" -type d -name "lnInclude" | while read -r ln_dir; do
    rel="${ln_dir#${SRC}/}"
    dst_ln="${OUT_DIR}/src/${rel}"
    if [[ -d "${ln_dir}" ]]; then
        mkdir -p "${dst_ln}"
        # Resolve symlinks to real files
        find "${ln_dir}" -maxdepth 1 -type l -o -type f | while read -r link; do
            real="$(realpath "${link}" 2>/dev/null || true)"
            if [[ -f "${real}" && "${real}" == "${SRC}/"* ]]; then
                cp -n "${real}" "${dst_ln}/$(basename "${link}")" 2>/dev/null || true
            fi
        done
    fi
done

echo "[4] Copying solver source ..."
cp -r "${SOLVER_DIR}" "${OUT_DIR}/solver"

echo ""
echo "Done. Vendor tree at: ${OUT_DIR}"
echo "Total files:"
find "${OUT_DIR}" -type f | wc -l

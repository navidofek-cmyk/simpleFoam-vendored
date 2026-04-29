#!/usr/bin/env bash
# Runs inside a Docker container with OpenFOAM-10 installed.
# 1. Parses Make/files for each OF module simpleFoam needs.
# 2. Copies all required .C and .H source files to vendor/.
# 3. Recreates lnInclude flat dirs.
# 4. Writes vendor/sources.cmake — exact list of .C files to compile.
set -eo pipefail

OF_ROOT="${WM_PROJECT_DIR:-/opt/openfoam10}"
SOLVER_DIR="/work/solver"
OUT_DIR="/out/vendor"

set +eu
# shellcheck disable=SC1091
source "${OF_ROOT}/etc/bashrc"
set -eu

SRC="${FOAM_SRC}"

# Modules that simpleFoam links against (mirrors Make/options EXE_LIBS)
MODULES=(
    "OpenFOAM"
    "OSspecific/POSIX"
    "Pstream/mpi"
    "finiteVolume"
    "meshTools"
    "physicalProperties"
    "MomentumTransportModels/momentumTransportModels"
    "MomentumTransportModels/incompressible"
    "sampling"
    "fvModels"
    "fvConstraints"
)

echo "[1] Parsing Make/files for each module ..."
: > /tmp/sources_raw.txt

parse_make_files() {
    local module_dir="$1"
    local make_file="${module_dir}/Make/files"
    [[ -f "${make_file}" ]] || { echo "    WARNING: no Make/files in ${module_dir}"; return; }

    python3 - "${module_dir}" "${make_file}" "${OUT_DIR}/src" "${SRC}" <<'PYEOF'
import sys, re, os

module_dir = sys.argv[1]
make_file  = sys.argv[2]
# sys.argv[3] = vendor/src output dir (for .Cver files)
# sys.argv[4] = OF SRC root (for relative path calculation)

variables = {}

def expand(s, variables):
    prev = None
    while prev != s:
        prev = s
        for k, v in variables.items():
            s = s.replace(f'$({k})', v)
    return s

with open(make_file) as fh:
    lines = fh.readlines()

for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    # Variable assignment: VAR = value  (not a source file line)
    m = re.match(r'^(\w+)\s*=\s*(.+)', line)
    if m and not line.endswith('.C'):
        # Expand the value using already-known variables, then store
        variables[m.group(1)] = expand(m.group(2).strip(), variables)
        continue
    # LIB / EXE target — skip
    if line.startswith('LIB') or line.startswith('EXE'):
        continue
    # Source file (may contain $(VAR))
    if line.endswith('.C') or line.endswith('.Cver'):
        expanded = expand(line, variables)
        abs_path = os.path.normpath(os.path.join(module_dir, expanded))
        # Handle .Cver files (unity builds with version string substitution)
        if expanded.endswith('.Cver'):
            cver_src = abs_path
            if os.path.isfile(cver_src):
                with open(cver_src) as f:
                    content = f.read()
                content = content.replace('VERSION_STRING', '10')
                content = content.replace('BUILD_STRING', 'vendored')
                # Write to vendor dir (can't write to read-only OF source)
                out_dir = sys.argv[3]
                rel = os.path.relpath(cver_src, sys.argv[4])
                cver_dst = os.path.join(out_dir, rel[:-4] + 'ver.C')
                os.makedirs(os.path.dirname(cver_dst), exist_ok=True)
                with open(cver_dst, 'w') as f:
                    f.write(content)
                print(cver_dst)
            else:
                print(f"MISSING: {cver_src}", file=sys.stderr)
        elif os.path.isfile(abs_path):
            print(abs_path)
        else:
            print(f"MISSING: {abs_path}", file=sys.stderr)
PYEOF
}

for mod in "${MODULES[@]}"; do
    module_dir="${SRC}/${mod}"
    echo "    ${mod}"
    parse_make_files "${module_dir}" >> /tmp/sources_raw.txt
done

TOTAL=$(wc -l < /tmp/sources_raw.txt)
echo "    Total source files from Make/files: ${TOTAL}"

echo "[2] Collecting all headers via g++ -MM ..."
INCLUDES=(
    -I"${SOLVER_DIR}"
    -I"${SRC}/OpenFOAM/lnInclude"
    -I"${SRC}/OSspecific/POSIX/lnInclude"
    -I"${SRC}/Pstream/mpi/lnInclude"
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

g++ -MM "${INCLUDES[@]}" "${SOLVER_DIR}/simpleFoam.C" 2>/dev/null \
    | tr ' \\' '\n' \
    | grep "^${OF_ROOT}" \
    | sort -u > /tmp/of_headers.txt

HEADER_COUNT=$(wc -l < /tmp/of_headers.txt)
echo "    Found ${HEADER_COUNT} OF headers."

echo "[3] Copying source files ..."
mkdir -p "${OUT_DIR}/src"
COPIED_C=0
: > /tmp/sources_list.txt

while IFS= read -r abs_src; do
    # .Cver files were already written to vendor by the parser — just record path
    if [[ "${abs_src}" == "${OUT_DIR}/src/"* ]]; then
        rel="${abs_src#${OUT_DIR}/}"
        echo "${rel}" >> /tmp/sources_list.txt
        COPIED_C=$((COPIED_C + 1))
        continue
    fi
    rel="${abs_src#${SRC}/}"
    dst="${OUT_DIR}/src/${rel}"
    mkdir -p "$(dirname "${dst}")"
    if cp -n "${abs_src}" "${dst}" 2>/dev/null; then
        COPIED_C=$((COPIED_C + 1))
        echo "src/${rel}" >> /tmp/sources_list.txt
    fi
done < /tmp/sources_raw.txt

echo "    Copied: ${COPIED_C} .C files"

echo "[4] Copying headers ..."
COPIED_H=0
while IFS= read -r hdr; do
    rel="${hdr#${SRC}/}"
    dst="${OUT_DIR}/src/${rel}"
    mkdir -p "$(dirname "${dst}")"
    cp -n "${hdr}" "${dst}" 2>/dev/null && COPIED_H=$((COPIED_H + 1)) || true
done < /tmp/of_headers.txt
echo "    Copied: ${COPIED_H} headers"

echo "[5] Recreating lnInclude flat dirs ..."
# Also include transitive header-only deps (needed as include paths but not compiled)
HEADER_ONLY_MODULES=(
    "triSurface"
    "surfMesh"
    "fileFormats"
    "dynamicMesh"
    "lagrangian/basic"
    "thermophysicalModels/specie"
    "thermophysicalModels/basic"
    "thermophysicalModels/solidThermo"
    "MomentumTransportModels/compressible"
    "ThermophysicalTransportModels"
    "conversion"
)
ALL_INC_MODULES=("${MODULES[@]}" "${HEADER_ONLY_MODULES[@]}")
for mod in "${ALL_INC_MODULES[@]}"; do
    ln_dir="${SRC}/${mod}/lnInclude"
    [[ -d "${ln_dir}" ]] || continue
    rel="${mod}/lnInclude"
    dst_ln="${OUT_DIR}/src/${rel}"
    mkdir -p "${dst_ln}"
    find "${ln_dir}" -maxdepth 1 \( -type l -o -type f \) | while read -r link; do
        real="$(realpath "${link}" 2>/dev/null || true)"
        [[ -f "${real}" ]] || continue
        cp -n "${real}" "${dst_ln}/$(basename "${link}")" 2>/dev/null || true
    done
done
# Also copy finiteVolume/cfdTools/general/include (non-lnInclude dir)
mkdir -p "${OUT_DIR}/src/finiteVolume/cfdTools/general/include"
find "${SRC}/finiteVolume/cfdTools/general/include" -maxdepth 1 -name "*.H" | \
    while read -r f; do
        cp -n "${f}" "${OUT_DIR}/src/finiteVolume/cfdTools/general/include/" 2>/dev/null || true
    done

echo "[6] Writing preamble.H and patching vendor files for standalone compilation ..."
cat > "${OUT_DIR}/preamble.H" <<'PREAMBLE'
// Standalone-build preamble: provides global declarations that wmake exposes
// implicitly through its library-wide include paths.
// Added via -include preamble.H in CMakeLists.txt.
#ifndef OF_STANDALONE_PREAMBLE_H
#define OF_STANDALONE_PREAMBLE_H
#include "OSspecific.H"
#include "IOstreams.H"
#include "OFstream.H"
#endif
PREAMBLE
# UPstream.C references Pstream:: which is a derived class — add forward include
UPSTREAM="${OUT_DIR}/src/OpenFOAM/lnInclude/UPstream.C"
if [[ -f "${UPSTREAM}" ]] && ! grep -q '"Pstream.H"' "${UPSTREAM}"; then
    python3 -c "
f = '${UPSTREAM}'
with open(f) as fh: c = fh.read()
with open(f, 'w') as fh:
    fh.write(c.replace('#include \"UPstream.H\"',
                        '#include \"UPstream.H\"\n#include \"Pstream.H\"', 1))
"
    echo "    Patched: UPstream.C"
fi

echo "[6b] Generating Flex-based parsers ..."
# readSTLASCII is implemented as a Flex grammar (.L) — must be generated before build
FLEX_L="${SRC}/triSurface/triSurface/interfaces/STL/readSTLASCII.L"
FLEX_DST="${OUT_DIR}/src/triSurface/lnInclude/readSTLASCII.C"
if [[ -f "${FLEX_L}" ]]; then
    flex -+ -f -o "${FLEX_DST}" "${FLEX_L}"
    echo "    Generated: readSTLASCII.C"
else
    echo "    WARNING: ${FLEX_L} not found"
fi

echo "[7] Copying solver source ..."
cp -r "${SOLVER_DIR}" "${OUT_DIR}/solver"

echo "[8] Writing sources.cmake manifest ..."
{
    echo "# Auto-generated by collect_deps.sh — do not edit"
    echo "set(OF_VENDOR_SOURCES"
    sort /tmp/sources_list.txt | while read -r f; do
        echo "    \${VENDOR_DIR}/${f}"
    done
    echo ")"
} > "${OUT_DIR}/sources.cmake"

MANIFEST_COUNT=$(grep -c "\.C$" "${OUT_DIR}/sources.cmake" || true)
echo "    Written: sources.cmake (${MANIFEST_COUNT} entries)"

echo ""
echo "Done. Vendor tree: ${OUT_DIR}"
echo "Total files: $(find "${OUT_DIR}" -type f | wc -l)"

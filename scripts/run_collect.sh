#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE="openfoam10-base:latest"

if ! docker image inspect "${IMAGE}" &>/dev/null; then
    echo "[run_collect] Image ${IMAGE} not found, building ..."
    docker build -f "${PROJECT_ROOT}/Dockerfile.base" -t "${IMAGE}" "${PROJECT_ROOT}"
fi

echo "[run_collect] Running dependency collection inside container ..."
mkdir -p "${PROJECT_ROOT}/vendor"

docker run --rm \
    -v "${PROJECT_ROOT}/solver:/work/solver:ro" \
    -v "${PROJECT_ROOT}/vendor:/out/vendor" \
    -v "${SCRIPT_DIR}/collect_deps.sh:/collect_deps.sh:ro" \
    "${IMAGE}" \
    bash /collect_deps.sh

echo ""
echo "[run_collect] vendor/ populated:"
find "${PROJECT_ROOT}/vendor" -type f | wc -l
echo "files total"
du -sh "${PROJECT_ROOT}/vendor"

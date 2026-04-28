#!/usr/bin/env bash
# Runs collect_deps.sh inside a temporary OF-10 container.
# Result lands in ./vendor/ on the host.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

docker run --rm \
    -v "${PROJECT_ROOT}/solver:/work/solver:ro" \
    -v "${PROJECT_ROOT}/vendor:/out/vendor" \
    -v "${SCRIPT_DIR}/collect_deps.sh:/collect_deps.sh:ro" \
    openfoam10-base:latest \
    bash /collect_deps.sh

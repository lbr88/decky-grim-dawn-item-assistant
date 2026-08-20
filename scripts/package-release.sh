#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_root="${repo_root}/dist-release"
archive="${release_root}/decky-grim-dawn-item-assistant.zip"
stage_root="$(mktemp -d /tmp/decky-gdia-release.XXXXXX)"
plugin_root="${stage_root}/decky-grim-dawn-item-assistant"

cleanup() {
    rm -rf -- "${stage_root}"
}
trap cleanup EXIT

if [[ ! -f "${repo_root}/dist/index.js" ]]; then
    echo "Missing dist/index.js; run pnpm run build first." >&2
    exit 1
fi

mkdir -p "${plugin_root}/backend" "${plugin_root}/dist" \
    "${plugin_root}/assets" "${release_root}"

install -m 0644 "${repo_root}/dist/index.js" "${plugin_root}/dist/index.js"
install -m 0644 "${repo_root}/main.py" "${plugin_root}/main.py"
install -m 0644 "${repo_root}/plugin.json" "${plugin_root}/plugin.json"
install -m 0644 "${repo_root}/package.json" "${plugin_root}/package.json"
install -m 0644 "${repo_root}/README.md" "${plugin_root}/README.md"
install -m 0644 "${repo_root}/LICENSE" "${plugin_root}/LICENSE"
install -m 0644 "${repo_root}/THIRD_PARTY_NOTICES.md" \
    "${plugin_root}/THIRD_PARTY_NOTICES.md"
install -m 0644 "${repo_root}/assets/logo.svg" "${plugin_root}/assets/logo.svg"

for module in __init__ bridge controller inventory models paths processes; do
    install -m 0644 "${repo_root}/backend/${module}.py" \
        "${plugin_root}/backend/${module}.py"
done

rm -f -- "${archive}"
(cd "${stage_root}" && python3 -m zipfile -c "${archive}" decky-grim-dawn-item-assistant)
printf '%s\n' "${archive}"

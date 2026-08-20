#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
upstream_root="${1:-}"
expected_commit="b6f4e6f0fbb8f9b43d92af2f1380ef2a6f8eb1cb"

if [[ -z "${upstream_root}" ]] || ! git -C "${upstream_root}" rev-parse --git-dir >/dev/null 2>&1; then
    echo "Usage: $0 /path/to/iagd" >&2
    exit 2
fi

actual_commit="$(git -C "${upstream_root}" rev-parse HEAD)"
if [[ "${actual_commit}" != "${expected_commit}" ]]; then
    echo "Unsupported Item Assistant commit: ${actual_commit}" >&2
    echo "Expected: ${expected_commit}" >&2
    exit 3
fi

git -C "${upstream_root}" diff --quiet
git -C "${upstream_root}" diff --cached --quiet

patch_file="${repo_root}/patches/item-assistant-decky-bridge.patch"
git -C "${upstream_root}" apply --check "${patch_file}"
git -C "${upstream_root}" apply "${patch_file}"
install -m 0644 \
    "${repo_root}/bridge/DeckyBridgeController.cs" \
    "${upstream_root}/IAGrim/UI/Controller/DeckyBridgeController.cs"

echo "Applied Decky bridge to Item Assistant ${expected_commit}"

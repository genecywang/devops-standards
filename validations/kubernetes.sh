#!/usr/bin/env bash
set -euo pipefail

# Select manifests before requiring a validator. Helm sources need rendering first.
manifest_files=()
file_list="$(mktemp)"
trap 'rm -f "$file_list"' EXIT
find . \( -name .git -o -name .claude -o -name .codex -o -name node_modules -o -name vendor -o -path './docs/archive' \) -prune -o -type f \( -name '*.yaml' -o -name '*.yml' \) -print0 > "$file_list"
while IFS= read -r -d '' file; do
  parent="$(dirname "$file")"
  in_chart=0
  while :; do
    if [ -f "$parent/Chart.yaml" ]; then in_chart=1; break; fi
    [ "$parent" != . ] || break
    parent="$(dirname "$parent")"
  done
  [ "$in_chart" -eq 0 ] || continue
  if grep -Eq '^(apiVersion|kind):' "$file"; then
    manifest_files+=("$file")
  else
    status=$?
    [ "$status" -eq 1 ] || { echo "kubernetes: cannot inspect $file" >&2; exit "$status"; }
  fi
done < "$file_list"

if [ "${#manifest_files[@]}" -eq 0 ]; then
  echo "kubernetes: no YAML manifests found, skipping"
  exit 0
fi
if ! command -v kubeconform >/dev/null 2>&1; then
  echo "kubernetes: kubeconform not found (required for schema validation)" >&2
  exit 1
fi
for file in "${manifest_files[@]}"; do
  echo "kubernetes: kubeconform $file"
  kubeconform -strict "$file"
done

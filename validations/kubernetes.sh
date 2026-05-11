#!/usr/bin/env bash
set -euo pipefail

manifest_files="$(find . -path './.git' -prune -o -path './openspec/*' -prune -o -path './.claude/*' -prune -o -path './.codex/*' -prune -o \( -name '*.yaml' -o -name '*.yml' \) -print | sort)"

if [ -z "$manifest_files" ]; then
  echo "kubernetes: no YAML manifests found, skipping"
  exit 0
fi

if command -v kubeconform >/dev/null 2>&1; then
  echo "$manifest_files" | while IFS= read -r file; do
    if grep -q '^apiVersion:' "$file"; then
      echo "kubernetes: kubeconform $file"
      kubeconform -strict "$file"
    fi
  done
  exit 0
fi

if command -v kubectl >/dev/null 2>&1; then
  echo "$manifest_files" | while IFS= read -r file; do
    if grep -q '^apiVersion:' "$file"; then
      echo "kubernetes: kubectl dry-run $file"
      kubectl apply --dry-run=client -f "$file" >/dev/null
    fi
  done
  exit 0
fi

echo "kubernetes: kubeconform and kubectl not found"
exit 1

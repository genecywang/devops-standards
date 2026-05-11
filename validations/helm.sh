#!/usr/bin/env bash
set -euo pipefail

if ! find . -path './.git' -prune -o -name 'Chart.yaml' -print -quit | grep -q .; then
  echo "helm: no Chart.yaml files found, skipping"
  exit 0
fi

if ! command -v helm >/dev/null 2>&1; then
  echo "helm: command not found"
  exit 1
fi

find . -path './.git' -prune -o -name 'Chart.yaml' -print \
  | sed 's#/Chart.yaml$##' \
  | sort -u \
  | while IFS= read -r chart; do
      echo "helm: lint $chart"
      helm lint "$chart"
      echo "helm: template $chart"
      helm template validation "$chart" >/dev/null
    done

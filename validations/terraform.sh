#!/usr/bin/env bash
set -euo pipefail

if ! find . -path './.git' -prune -o -name '*.tf' -print -quit | grep -q .; then
  echo "terraform: no .tf files found, skipping"
  exit 0
fi

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform: command not found"
  exit 1
fi

echo "terraform: fmt check"
terraform fmt -check -recursive

echo "terraform: validate modules"
find . -path './.git' -prune -o -path '*/.terraform/*' -prune -o -name '*.tf' -print \
  | sed 's#/[^/]*$##' \
  | sort -u \
  | while IFS= read -r dir; do
      [ -n "$dir" ] || dir="."
      echo "terraform: validate $dir"
      terraform -chdir="$dir" validate -no-color
    done

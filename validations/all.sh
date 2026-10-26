#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

scripts=(
  "$script_dir/terraform.sh"
  "$script_dir/helm.sh"
  "$script_dir/kubernetes.sh"
  "$script_dir/iam.sh"
)

for script in "${scripts[@]}"; do
  echo "==> $script"
  bash "$script"
done

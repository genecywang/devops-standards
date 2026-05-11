#!/usr/bin/env bash
set -euo pipefail

scripts=(
  "validations/terraform.sh"
  "validations/helm.sh"
  "validations/kubernetes.sh"
  "validations/iam.sh"
)

for script in "${scripts[@]}"; do
  echo "==> $script"
  bash "$script"
done

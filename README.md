# devops-standards

Personal DevOps standards, Claude Code configuration, and security guardrails for AWS, Kubernetes, and CI/CD workflows.

## Contents

| File | Description |
|---|---|
| `CLAUDE.md` | Claude Code behavior rules — loaded automatically on every conversation |
| `setup/claude-code-macos.md` | New machine setup guide for Claude Code on macOS |

## Planning

- [Platform Foundation](docs/platform-foundation/README.md)

## New Machine Setup

Clone this repo and hand `setup/claude-code-macos.md` to Claude Code:

```zsh
git clone https://github.com/genecywang/devops-standards.git
cd devops-standards
# Open Claude Code, then:
# "Help me run setup/claude-code-macos.md"
```

This sets up:
- `rm` → `trash` (recoverable deletes)
- Dangerous command deny list (15 rules)
- Status line (model, context bar, rate limits, git info)
- `cc` launcher with permission mode selector

## Tech Stack

AWS (EKS, RDS, S3, IAM, MSK) · Kubernetes (Helm, Karpenter) · Terraform · Jenkins · ArgoCD · KEDA · Prometheus · Fluent-bit · OpenSearch

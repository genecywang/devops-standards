# Self-Service Ops Copilot

Phase 1 MVP for Slack `Socket Mode` ingress on top of `openclaw_foundation`.

## Local Smoke Test

Prerequisites:

- `SLACK_BOT_TOKEN`
- `SLACK_APP_TOKEN`
- `self_service_copilot/.venv`
- `openclaw_foundation` installed editable into the venv

Run from this repo root:

```bash
cd self_service_copilot
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_APP_TOKEN="xapp-..."
export COPILOT_CLUSTER="staging-main"
export COPILOT_ENVIRONMENT="staging"
export COPILOT_ALLOWED_CLUSTERS="staging-main"
export COPILOT_ALLOWED_NAMESPACES="payments"
export COPILOT_ALLOWED_CHANNEL_IDS="C03F4JWGJGK"
export COPILOT_PROVIDER="fake"
.venv/bin/python -m self_service_copilot.bot
```

Then mention the bot in Slack:

```text
@copilot get_pod_status payments payments-api-123
```

Environment-aware grammar for shared channels:

```text
@copilot au get_pod_status payments payments-api-123
@copilot jp get_deployment_restart_rate dev dev-py3-h2s-apisvc
```

When no environment prefix is provided, the bot uses the default configured environment.
When you need to explicitly verify a specific environment during manual testing, prefer the environment-prefixed form.

## Ownership Gate

Each deployed bot instance owns only its own identity:

- `COPILOT_ENVIRONMENT`
- `COPILOT_CLUSTER`

Current routing rules:

- manual command without environment prefix: follow the existing default-environment path
- manual command with environment prefix: another environment is ignored without a Slack reply
- normalized Prometheus alert: matched by `Cluster:` first
- Prometheus alert for another cluster: ignored without a Slack reply
- Prometheus alert for the same cluster: filtered locally only; no auto-investigation reply yet

Expected thread reply:

```text
[success] get_pod_status payments/payments-api-123
pod payments-api-123 is Running
```

For `real` Kubernetes provider mode:

```bash
export COPILOT_PROVIDER="real"
```

This uses the same config loading path as `openclaw_foundation`:

- first `in-cluster`
- then local `kubeconfig`

Optional rate limit env vars:

- `COPILOT_USER_RATE_LIMIT_COUNT` (default: `5`)
- `COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `COPILOT_CHANNEL_RATE_LIMIT_COUNT` (default: `20`)
- `COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)

Optional multi-environment env vars:

- `COPILOT_DEFAULT_ENVIRONMENT` (defaults to `COPILOT_ENVIRONMENT`)
- `COPILOT_ENVIRONMENT_CLUSTERS` format:
  `staging=staging-main,au=au-main,jp=jp-main`

Supported tools:

- `get_pod_status`
- `get_pod_events`
- `get_deployment_status`
- `get_pod_runtime`
- `get_pod_cpu_usage`
- `get_deployment_restart_rate`

Known MVP limits:

- plain text replies only
- no Slack integration test yet
- no retry on Slack SDK send failure
- empty `COPILOT_ALLOWED_CHANNEL_IDS` means no channel restriction
- no per-user / per-channel throttle yet

## Image CI

GitHub Actions workflow:

- PR: run pytest + docker build, do not push image
- `main` push: run pytest + docker build + push to `GHCR`
- `workflow_dispatch`: manual build + push `sha-*` tag

Published image tags:

- `ghcr.io/<owner>/self-service-copilot:sha-<shortsha>`
- `ghcr.io/<owner>/self-service-copilot:latest` (`main` only)

## Manual Deploy

After CI publishes an image, deploy manually with Helm:

```bash
helm upgrade --install staging-copilot deploy/charts/self-service-copilot/ \
  --namespace <namespace> \
  --set image.repository=ghcr.io/<owner>/self-service-copilot \
  --set image.tag=sha-<shortsha> \
  --set config.cluster=<cluster> \
  --set config.allowedNamespaces=<ns1,ns2> \
  --set slack.secretName=self-service-copilot-slack
```

## Staging Validation

After deploy, validate these three paths.

### 1. Env wiring

Check rate limit env vars inside the pod:

```bash
kubectl exec -n <namespace> deploy/<copilot-deployment> -- printenv | rg 'COPILOT_(USER|CHANNEL)_RATE_LIMIT'
```

Expected:

```text
COPILOT_USER_RATE_LIMIT_COUNT=5
COPILOT_USER_RATE_LIMIT_WINDOW_SECONDS=60
COPILOT_CHANNEL_RATE_LIMIT_COUNT=20
COPILOT_CHANNEL_RATE_LIMIT_WINDOW_SECONDS=60
```

### 2. Happy path

In an allowed Slack channel, run:

```text
@copilot get_pod_status <namespace> <pod_name>
```

Expected:

- bot replies with `[success]`
- pod logs do not contain `rate limit exceeded`

### 3. Throttle path

From the same Slack user, send more than 5 requests within 60 seconds:

```text
@copilot get_pod_status <namespace> <pod_name>
```

Expected on the 6th request:

```text
[denied] rate limit exceeded, please retry later
```

Confirm pod log:

```bash
kubectl logs -n <namespace> deploy/<copilot-deployment> --since=10m | rg 'rate limit exceeded'
```

Expected:

```text
rate limit exceeded for actor=U... channel=C...
```

To validate `per-channel` throttling, have multiple users send requests in the same channel until total requests exceed 20 within 60 seconds.

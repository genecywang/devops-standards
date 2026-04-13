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

Known MVP limits:

- only `get_pod_status` and `get_pod_events`
- plain text replies only
- no Slack integration test yet
- no retry on Slack SDK send failure
- empty `COPILOT_ALLOWED_CHANNEL_IDS` means no channel restriction

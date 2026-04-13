# Self-Service Copilot Deploy Design

**Date:** 2026-04-13
**Scope:** Dockerfile + Helm chart for `self_service_copilot`
**Status:** Approved

## Context

`self_service_copilot` 是 Slack Socket Mode bot，底層依賴 `openclaw_foundation`。
功能 MVP 已完成（4 個 read-only tools、end-to-end Slack 驗證），目前缺少可部署形態。

## Non-Goals

- Ingress / HPA / PodDisruptionBudget
- HTTP health server
- Readiness probe
- Secret lifecycle 管理（由外部建立）
- Per-namespace RBAC hardening（Phase 2）

---

## 1. Dockerfile

**位置：** `self_service_copilot/Dockerfile`
**Build context：** repo root（需同時打包 `openclaw_foundation`）

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY openclaw_foundation/ ./openclaw_foundation/
COPY self_service_copilot/ ./self_service_copilot/

RUN python -m pip install --no-cache-dir \
    ./openclaw_foundation \
    ./self_service_copilot

RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "self_service_copilot.bot"]
```

**`.dockerignore`（repo root）：**

```
**/.venv
**/__pycache__
**/*.egg-info
**/tests
**/.DS_Store
```

Single-stage。不暴露 port（Socket Mode 純 outbound）。

---

## 2. Helm Chart

**位置：** `deploy/charts/self-service-copilot/`

```
Chart.yaml
values.yaml
templates/
  _helpers.tpl
  serviceaccount.yaml
  clusterrole.yaml
  clusterrolebinding.yaml
  configmap.yaml
  deployment.yaml
```

不加 `secret.yaml`：Secret 由外部建立，Deployment 用 `secretKeyRef` 引用。

### Chart.yaml

```yaml
apiVersion: v2
name: self-service-copilot
description: Self-Service Ops Copilot Slack bot
type: application
version: 0.1.0
appVersion: "0.1.0"
```

### values.yaml 關鍵欄位

```yaml
image:
  repository: ghcr.io/example/self-service-copilot
  tag: dev
  pullPolicy: IfNotPresent

config:
  cluster: staging-main
  environment: staging
  allowedClusters: staging-main
  allowedNamespaces: payments
  allowedChannelIds: ""
  provider: fake
  prometheusBaseUrl: ""
  logLevel: INFO

slack:
  secretName: self-service-copilot-slack   # pre-created externally
  botTokenKey: SLACK_BOT_TOKEN
  appTokenKey: SLACK_APP_TOKEN

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

---

## 3. ConfigMap env vars

全部非敏感設定走 ConfigMap，由 Helm values 注入：

| 變數 | values key |
|------|-----------|
| `COPILOT_CLUSTER` | `config.cluster` |
| `COPILOT_ENVIRONMENT` | `config.environment` |
| `COPILOT_ALLOWED_CLUSTERS` | `config.allowedClusters` |
| `COPILOT_ALLOWED_NAMESPACES` | `config.allowedNamespaces` |
| `COPILOT_ALLOWED_CHANNEL_IDS` | `config.allowedChannelIds` |
| `COPILOT_PROVIDER` | `config.provider` |
| `OPENCLAW_PROMETHEUS_BASE_URL` | `config.prometheusBaseUrl` |
| `LOG_LEVEL` | `config.logLevel` |

Slack tokens 由外部 Secret 提供，Deployment 用 `envFrom` (configmap) + 兩個 `env[].valueFrom.secretKeyRef`。

### prometheusBaseUrl 必填約束

`config.prometheusBaseUrl` 預設空字串，對 `provider=fake` 無影響。
`provider=real` 時若值為空，`bot.py:build_registry()` 會在啟動時拋出 `ValueError`，pod 立即 crash。

為避免 runtime 才炸，Helm template 加 fail-fast 檢查：

```yaml
{{- if and (eq .Values.config.provider "real") (not .Values.config.prometheusBaseUrl) }}
{{- fail "config.prometheusBaseUrl is required when config.provider is \"real\"" }}
{{- end }}
```

這讓問題在 `helm install / upgrade` 時就報錯，不讓 pod 起來再炸。

### LOG_LEVEL 生效方式

`bot.py` 的 `logging.basicConfig` 目前寫死 `level=logging.INFO`。
此輪同步修改 `bot.py`，改為讀取 `LOG_LEVEL` env var：

```python
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
```

這讓 Helm 推入的 `LOG_LEVEL` 真正生效，不用重建 image 就能切換 DEBUG / WARNING。

---

## 4. RBAC

**ClusterRole**（最小 read-only）：

```yaml
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/status", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "deployments/status"]
    verbs: ["get", "list", "watch"]
```

`deployments/status` 明確列出，避免部分 cluster auth 實作的 subresource 隔離問題。

**ClusterRoleBinding** bind 到 `self-service-copilot` ServiceAccount。

**二階段 RBAC hardening（Phase 2）：**
待 `allowed_namespaces` 集合穩定後，改為 per-namespace Role + RoleBinding，移除 ClusterRole。

---

## 5. Liveness Probe

不加 readiness probe。Liveness 使用 Python exec，讀取 `/proc/1/cmdline` 確認主程式存活：

```yaml
livenessProbe:
  exec:
    command:
      - python
      - -c
      - |
        import pathlib, sys
        cmdline = pathlib.Path("/proc/1/cmdline").read_text()
        sys.exit(0 if "self_service_copilot.bot" in cmdline else 1)
  initialDelaySeconds: 30
  periodSeconds: 30
  failureThreshold: 3
```

不依賴 `pgrep` / `procps`，`python:3.11-slim` 內建即可執行。

---

## 6. Deployment 關鍵結構

```yaml
spec:
  replicas: 1
  template:
    spec:
      serviceAccountName: self-service-copilot
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: self-service-copilot
          image: {{ .Values.image.repository }}:{{ .Values.image.tag }}
          envFrom:
            - configMapRef:
                name: self-service-copilot-config
          env:
            - name: SLACK_BOT_TOKEN
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.slack.secretName }}
                  key: {{ .Values.slack.botTokenKey }}
            - name: SLACK_APP_TOKEN
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.slack.secretName }}
                  key: {{ .Values.slack.appTokenKey }}
          resources: {{ toYaml .Values.resources | nindent 12 }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          livenessProbe: ...
```

---

## 檔案清單

新增：

```
self_service_copilot/Dockerfile
.dockerignore                                          # repo root
deploy/charts/self-service-copilot/Chart.yaml
deploy/charts/self-service-copilot/values.yaml
deploy/charts/self-service-copilot/templates/_helpers.tpl
deploy/charts/self-service-copilot/templates/serviceaccount.yaml
deploy/charts/self-service-copilot/templates/clusterrole.yaml
deploy/charts/self-service-copilot/templates/clusterrolebinding.yaml
deploy/charts/self-service-copilot/templates/configmap.yaml
deploy/charts/self-service-copilot/templates/deployment.yaml
```

修改：

```
self_service_copilot/src/self_service_copilot/bot.py   # LOG_LEVEL env var 讀取
```

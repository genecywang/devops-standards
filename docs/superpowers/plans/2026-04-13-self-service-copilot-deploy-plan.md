# Self-Service Copilot Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 `self_service_copilot` 建立可部署形態：Dockerfile、.dockerignore、Helm chart（含 RBAC、ConfigMap、Deployment），並讓 `LOG_LEVEL` env var 真正生效。

**Architecture:** `self_service_copilot` 與 `openclaw_foundation` 從 repo root 一起打包進 single-stage Docker image；Helm chart 管理 K8s 資源，Secret 由外部預建；bot.py 新增 `_log_level_from_env()` helper 讓 log level 可由 ConfigMap 控制。

**Tech Stack:** Python 3.11-slim, Helm 3, Kubernetes RBAC, Slack Socket Mode (outbound only)

---

## File Structure

| 狀態 | 路徑 | 責任 |
|------|------|------|
| 修改 | `self_service_copilot/src/self_service_copilot/bot.py` | 新增 `_log_level_from_env()`，wire 到 `main()` |
| 修改 | `self_service_copilot/tests/test_bot.py` | 補 3 個 `_log_level_from_env` 的 unit test |
| 新增 | `self_service_copilot/Dockerfile` | Image build，build context = repo root |
| 新增 | `.dockerignore` | 排掉 `.venv`, `__pycache__`, `*.egg-info`, `tests/`, `.DS_Store` |
| 新增 | `deploy/charts/self-service-copilot/Chart.yaml` | Chart metadata |
| 新增 | `deploy/charts/self-service-copilot/values.yaml` | 所有可調參數的 default |
| 新增 | `deploy/charts/self-service-copilot/templates/_helpers.tpl` | name / fullname / labels helpers |
| 新增 | `deploy/charts/self-service-copilot/templates/serviceaccount.yaml` | ServiceAccount |
| 新增 | `deploy/charts/self-service-copilot/templates/clusterrole.yaml` | read-only ClusterRole |
| 新增 | `deploy/charts/self-service-copilot/templates/clusterrolebinding.yaml` | ClusterRoleBinding |
| 新增 | `deploy/charts/self-service-copilot/templates/configmap.yaml` | 非敏感 env vars + fail-fast guard |
| 新增 | `deploy/charts/self-service-copilot/templates/deployment.yaml` | Deployment + liveness probe |

---

## Task 1: bot.py — LOG_LEVEL env reading

**Files:**
- Modify: `self_service_copilot/src/self_service_copilot/bot.py:94`
- Test: `self_service_copilot/tests/test_bot.py`

- [ ] **Step 1: 寫 3 個 failing tests**

在 `self_service_copilot/tests/test_bot.py` 尾端加入：

```python
def test_log_level_from_env_defaults_to_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    from importlib import reload
    import self_service_copilot.bot as bot_module
    reload(bot_module)
    assert bot_module._log_level_from_env() == logging.INFO


def test_log_level_from_env_reads_debug(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    from importlib import reload
    import self_service_copilot.bot as bot_module
    reload(bot_module)
    assert bot_module._log_level_from_env() == logging.DEBUG


def test_log_level_from_env_falls_back_to_info_for_invalid(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "NOTAVALIDLEVEL")
    from importlib import reload
    import self_service_copilot.bot as bot_module
    reload(bot_module)
    assert bot_module._log_level_from_env() == logging.INFO
```

也在該測試檔案頂部確認 `import logging` 已存在（`test_bot.py` 目前只 import `KubernetesResourceNotFoundError` 等，需補 `import logging`）。

- [ ] **Step 2: 確認 tests 目前 fail**

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_bot.py -k "log_level" -v
```

Expected: `AttributeError: module 'self_service_copilot.bot' has no attribute '_log_level_from_env'`

- [ ] **Step 3: 實作 `_log_level_from_env` 並 wire 進 `main()`**

在 `self_service_copilot/src/self_service_copilot/bot.py` 的 `logger = logging.getLogger(__name__)` 下方新增：

```python
def _log_level_from_env() -> int:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)
```

修改 `main()` 的第一行，從：

```python
    logging.basicConfig(level=logging.INFO)
```

改為：

```python
    logging.basicConfig(level=_log_level_from_env())
```

- [ ] **Step 4: 確認 tests pass**

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/test_bot.py -v
```

Expected: 全部 pass（原有 8 個 + 新增 3 個，共 11 個）

- [ ] **Step 5: Commit**

```bash
git add self_service_copilot/src/self_service_copilot/bot.py \
        self_service_copilot/tests/test_bot.py
git commit -m "feat: read LOG_LEVEL from env in bot main"
```

---

## Task 2: Dockerfile + .dockerignore

**Files:**
- Create: `self_service_copilot/Dockerfile`
- Create: `.dockerignore` (repo root)

- [ ] **Step 1: 建立 `self_service_copilot/Dockerfile`**

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

注意：
- build context 是 repo root，不是 `self_service_copilot/`
- 不 `EXPOSE` 任何 port（Socket Mode 純 outbound）

- [ ] **Step 2: 建立 `.dockerignore`（repo root）**

```
**/.venv
**/__pycache__
**/*.egg-info
**/tests
**/.DS_Store
```

- [ ] **Step 3: 驗證 Dockerfile 語法**

如果本機有 Docker，從 repo root 執行（只 build，不 push）：

```bash
docker build -f self_service_copilot/Dockerfile -t self-service-copilot:local . --no-cache
```

Expected: `Successfully built <image_id>`（會下載 python:3.11-slim，約 1-2 分鐘）

若本機無 Docker，改用語法檢查：

```bash
docker build --help > /dev/null && echo "docker available" || echo "docker not available"
```

- [ ] **Step 4: Commit**

```bash
git add self_service_copilot/Dockerfile .dockerignore
git commit -m "feat: add Dockerfile and dockerignore for self-service-copilot"
```

---

## Task 3: Helm chart scaffold (Chart.yaml + values.yaml + _helpers.tpl)

**Files:**
- Create: `deploy/charts/self-service-copilot/Chart.yaml`
- Create: `deploy/charts/self-service-copilot/values.yaml`
- Create: `deploy/charts/self-service-copilot/templates/_helpers.tpl`

- [ ] **Step 1: 建立目錄結構**

```bash
mkdir -p deploy/charts/self-service-copilot/templates
```

- [ ] **Step 2: 建立 `deploy/charts/self-service-copilot/Chart.yaml`**

```yaml
apiVersion: v2
name: self-service-copilot
description: Self-Service Ops Copilot Slack bot
type: application
version: 0.1.0
appVersion: "0.1.0"
```

- [ ] **Step 3: 建立 `deploy/charts/self-service-copilot/values.yaml`**

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
  # Name of the pre-created Kubernetes Secret containing Slack tokens.
  # Must be created externally before helm install.
  secretName: self-service-copilot-slack
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

- [ ] **Step 4: 建立 `deploy/charts/self-service-copilot/templates/_helpers.tpl`**

```
{{- define "self-service-copilot.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "self-service-copilot.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "self-service-copilot.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "self-service-copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "self-service-copilot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "self-service-copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

- [ ] **Step 5: helm lint 確認 scaffold 無錯**

```bash
helm lint deploy/charts/self-service-copilot/
```

Expected: `1 chart(s) linted, 0 chart(s) failed`

（此時 templates/ 只有 `_helpers.tpl`，lint 仍需通過）

- [ ] **Step 6: Commit**

```bash
git add deploy/charts/self-service-copilot/
git commit -m "feat: scaffold helm chart for self-service-copilot"
```

---

## Task 4: RBAC templates

**Files:**
- Create: `deploy/charts/self-service-copilot/templates/serviceaccount.yaml`
- Create: `deploy/charts/self-service-copilot/templates/clusterrole.yaml`
- Create: `deploy/charts/self-service-copilot/templates/clusterrolebinding.yaml`

- [ ] **Step 1: 建立 `templates/serviceaccount.yaml`**

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "self-service-copilot.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "self-service-copilot.labels" . | nindent 4 }}
```

- [ ] **Step 2: 建立 `templates/clusterrole.yaml`**

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: {{ include "self-service-copilot.fullname" . }}-reader
  labels:
    {{- include "self-service-copilot.labels" . | nindent 4 }}
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/status", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "deployments/status"]
    verbs: ["get", "list", "watch"]
```

- [ ] **Step 3: 建立 `templates/clusterrolebinding.yaml`**

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: {{ include "self-service-copilot.fullname" . }}-reader
  labels:
    {{- include "self-service-copilot.labels" . | nindent 4 }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {{ include "self-service-copilot.fullname" . }}-reader
subjects:
  - kind: ServiceAccount
    name: {{ include "self-service-copilot.fullname" . }}
    namespace: {{ .Release.Namespace }}
```

- [ ] **Step 4: helm template 確認渲染正確**

```bash
helm template staging-copilot deploy/charts/self-service-copilot/ \
  --namespace openclaw-system \
  --set slack.secretName=self-service-copilot-slack \
  | grep -A 5 "kind: ClusterRole"
```

Expected output（節錄）：

```
kind: ClusterRole
metadata:
  name: staging-copilot-self-service-copilot-reader
```

- [ ] **Step 5: Commit**

```bash
git add deploy/charts/self-service-copilot/templates/serviceaccount.yaml \
        deploy/charts/self-service-copilot/templates/clusterrole.yaml \
        deploy/charts/self-service-copilot/templates/clusterrolebinding.yaml
git commit -m "feat: add RBAC templates to self-service-copilot chart"
```

---

## Task 5: ConfigMap template（含 fail-fast guard）

**Files:**
- Create: `deploy/charts/self-service-copilot/templates/configmap.yaml`

- [ ] **Step 1: 建立 `templates/configmap.yaml`**

```yaml
{{- if and (eq .Values.config.provider "real") (not .Values.config.prometheusBaseUrl) }}
{{- fail "config.prometheusBaseUrl is required when config.provider is \"real\"" }}
{{- end }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "self-service-copilot.fullname" . }}-config
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "self-service-copilot.labels" . | nindent 4 }}
data:
  COPILOT_CLUSTER: {{ .Values.config.cluster | quote }}
  COPILOT_ENVIRONMENT: {{ .Values.config.environment | quote }}
  COPILOT_ALLOWED_CLUSTERS: {{ .Values.config.allowedClusters | quote }}
  COPILOT_ALLOWED_NAMESPACES: {{ .Values.config.allowedNamespaces | quote }}
  COPILOT_ALLOWED_CHANNEL_IDS: {{ .Values.config.allowedChannelIds | quote }}
  COPILOT_PROVIDER: {{ .Values.config.provider | quote }}
  OPENCLAW_PROMETHEUS_BASE_URL: {{ .Values.config.prometheusBaseUrl | quote }}
  LOG_LEVEL: {{ .Values.config.logLevel | quote }}
```

- [ ] **Step 2: 確認 fail-fast 在 real mode 無 URL 時生效**

```bash
helm template staging-copilot deploy/charts/self-service-copilot/ \
  --set config.provider=real \
  --set slack.secretName=self-service-copilot-slack
```

Expected: `Error: execution error at (self-service-copilot/templates/configmap.yaml:2:4): config.prometheusBaseUrl is required when config.provider is "real"`

- [ ] **Step 3: 確認 real mode 有 URL 時正常渲染**

```bash
helm template staging-copilot deploy/charts/self-service-copilot/ \
  --set config.provider=real \
  --set config.prometheusBaseUrl=http://prometheus.monitoring.svc.cluster.local:9090 \
  --set slack.secretName=self-service-copilot-slack \
  | grep -A 10 "kind: ConfigMap"
```

Expected：ConfigMap 正常渲染，`COPILOT_PROVIDER: "real"` 與 URL 都出現。

- [ ] **Step 4: Commit**

```bash
git add deploy/charts/self-service-copilot/templates/configmap.yaml
git commit -m "feat: add configmap template with provider=real fail-fast guard"
```

---

## Task 6: Deployment template

**Files:**
- Create: `deploy/charts/self-service-copilot/templates/deployment.yaml`

- [ ] **Step 1: 建立 `templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "self-service-copilot.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "self-service-copilot.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      {{- include "self-service-copilot.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "self-service-copilot.selectorLabels" . | nindent 8 }}
    spec:
      serviceAccountName: {{ include "self-service-copilot.fullname" . }}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          envFrom:
            - configMapRef:
                name: {{ include "self-service-copilot.fullname" . }}-config
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
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
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

- [ ] **Step 2: helm template 渲染完整 chart**

```bash
helm template staging-copilot deploy/charts/self-service-copilot/ \
  --namespace openclaw-system \
  --set slack.secretName=self-service-copilot-slack
```

Expected：輸出 6 個 YAML 文件（ServiceAccount, ClusterRole, ClusterRoleBinding, ConfigMap, Deployment），無錯誤。

- [ ] **Step 3: 確認 Deployment 中的 secretKeyRef 正確引用**

```bash
helm template staging-copilot deploy/charts/self-service-copilot/ \
  --namespace openclaw-system \
  --set slack.secretName=self-service-copilot-slack \
  | grep -A 4 "secretKeyRef"
```

Expected：

```yaml
          secretKeyRef:
            name: self-service-copilot-slack
            key: SLACK_BOT_TOKEN
...
          secretKeyRef:
            name: self-service-copilot-slack
            key: SLACK_APP_TOKEN
```

- [ ] **Step 4: Commit**

```bash
git add deploy/charts/self-service-copilot/templates/deployment.yaml
git commit -m "feat: add deployment template with liveness probe and secret refs"
```

---

## Task 7: 最終 helm lint 驗證

**Files:** 無新增

- [ ] **Step 1: helm lint 完整 chart**

```bash
helm lint deploy/charts/self-service-copilot/ \
  --set slack.secretName=self-service-copilot-slack
```

Expected: `1 chart(s) linted, 0 chart(s) failed`

- [ ] **Step 2: 確認全部 test 仍 pass**

```bash
cd self_service_copilot
.venv/bin/python -m pytest tests/ -q
```

Expected: `11 passed`

- [ ] **Step 3: 確認 git status 乾淨**

```bash
git status --short
```

Expected: 只有原本就存在的 `??` untracked files（backlog/、__pycache__/ 等），無 `M` 或 `A`。

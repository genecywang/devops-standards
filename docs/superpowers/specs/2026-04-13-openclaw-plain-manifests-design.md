# OpenClaw Plain Manifests Design

## Objective

在這個 repo 內建立一套最小可 `kubectl apply -f` 的 `OpenClaw on EKS` deployment 骨架，讓目前的 `openclaw_foundation/` runtime 能有對應的 Kubernetes manifests 落點。

這一版的目標不是完成 production-ready platform deployment，而是先把 stateless runtime、最小 RBAC、ConfigMap、NetworkPolicy 與 service wiring 固化成可維護的 plain manifests 結構。

## Scope

這一版只包含：

- `deploy/openclaw/` 目錄結構
- `Namespace`
- `ServiceAccount`
- `Role` / `RoleBinding`
- `ConfigMap`
- `Deployment`
- `Service`
- `NetworkPolicy`
- `PodDisruptionBudget`
- `README`

## Non-Goals

這一版不做：

- Helm chart
- Kustomize overlays
- `StatefulSet`
- `PVC`
- `Ingress`
- `HPA`
- `ExternalSecret`
- `ServiceMonitor`
- 真實 audit sink wiring
- ArgoCD application manifests

## Problem Statement

目前 `openclaw_foundation/` 已經有：

- Python runtime skeleton
- Kubernetes provider adapter
- real / fake provider mode
- domain error model

但 repo 內還沒有對應的 Kubernetes deployment 骨架，導致：

- runtime 最終要部署到哪裡只存在討論裡
- security boundary 缺少最小 manifests 表達
- 後續要轉 Helm chart 時沒有明確起點

## Approaches

### 1. Single Big YAML

把所有資源塞進一個大檔案。

優點：

- 最快

缺點：

- 很快變難維護
- 之後轉 Helm / Kustomize 比較痛

### 2. Plain Manifests Directory

每個 Kubernetes resource 一個檔案，集中在 `deploy/openclaw/`。

優點：

- 容易閱讀與維護
- 很適合之後轉 Helm
- 對目前階段最務實

缺點：

- 參數化能力不如 Helm

### 3. Kustomize First

一開始就做 base / overlay。

優點：

- 後續環境分層方便

缺點：

- 現在需求還不夠穩，會先增加複雜度

## Recommendation

採用 `Plain Manifests Directory`。

原因：

- 這和你目前想先用 `kubectl apply -f` 的需求一致
- 可以先把 deployment boundary 落成檔案
- 之後若要轉 Helm chart，這組 manifests 可以直接當模板來源

## Proposed Layout

```text
deploy/
  openclaw/
    README.md
    namespace.yaml
    serviceaccount.yaml
    role.yaml
    rolebinding.yaml
    configmap.yaml
    deployment.yaml
    service.yaml
    networkpolicy.yaml
    pdb.yaml
```

## Core Design

### Runtime Shape

`OpenClaw` 在這一版用：

- `Deployment`
- `ClusterIP Service`

不用：

- `StatefulSet`
- `PVC`

理由：

- 現在的 runtime 應維持 stateless
- pod 重建應該可接受
- audit / history / future queue state 應外部化，不應放 pod local storage

### Namespace

第一版先建立獨立 namespace，例如：

- `openclaw-system`

理由：

- 比較容易隔離 RBAC 與 NetworkPolicy
- 後續若要掛 IRSA 或 admission policy，也比較乾淨

### ServiceAccount

`serviceaccount.yaml` 需預留：

- IRSA annotation placeholder

但這一版不綁定特定 IAM role ARN。

### RBAC

`Role` / `RoleBinding` 先以 namespace-scope read-only 為主。

最小方向：

- `pods`
- `pods/status`
- `events`

verbs 只先給：

- `get`
- `list`
- `watch`

這樣能支撐目前 `get_pod_status`，也為下一步 `get_pod_events` 留足空間。

### ConfigMap

`configmap.yaml` 先放最小 runtime 設定，例如：

- `OPENCLAW_PROVIDER_MODE`
- `OPENCLAW_ALLOWED_CLUSTERS`
- `OPENCLAW_ALLOWED_NAMESPACES`
- `OPENCLAW_LOG_LEVEL`

這一版不做複雜 config loader，只表達 deployment contract。

### Deployment

`deployment.yaml` 應包含：

- 1 replica 起步
- 明確 `containerPort`
- environment variables 來自 `ConfigMap`
- `ServiceAccount`
- 基本 `resources`
- `readinessProbe`
- `livenessProbe`
- security context 採 least privilege baseline

這一版的 image 可先用 placeholder，例如：

- `ghcr.io/example/openclaw-foundation:dev`

但 README 要明確提醒需替換。

### Service

`service.yaml` 先提供：

- `ClusterIP`

只作為 cluster 內部呼叫入口，不對外暴露。

### NetworkPolicy

`networkpolicy.yaml` 先做最小骨架：

- 限制 ingress 到 namespace 內或指定 label caller
- 限制 egress 只到 DNS 與必要內部流量

這一版不追求完整 kube-apiserver CIDR 精準化，但要把「預設不完全開放」的意圖表達出來。

### PodDisruptionBudget

先給最小 `PDB`，避免 voluntary disruption 直接把 runtime 清空。

若 replica = 1，可用：

- `maxUnavailable: 1`

重點是先把 deploy artifact 補齊。

### README

`README.md` 需說清楚：

- manifests 用途
- 套用順序與 `kubectl apply -f deploy/openclaw/`
- image placeholder 要替換
- 這一版是 stateless runtime baseline，不含 PVC / Ingress / HPA

## Testing

至少需要：

- 檔案結構存在
- manifests 可做基本 YAML / schema smoke validation
- README 指令與檔案名稱一致

這一版不要求：

- 真實 apply 到 cluster
- live readiness verification

## Acceptance Criteria

完成時應能：

- 在 repo 內看到 `deploy/openclaw/` 最小 deployment 骨架
- 讓使用者可用 `kubectl apply -f deploy/openclaw/` 作為起點
- 清楚表達 stateless runtime、最小 RBAC、ConfigMap、NetworkPolicy 的基線
- 不引入 Helm / StatefulSet / PVC

## Risks

- 若現在就做太多 production 細節，會讓 manifests 骨架過重
- 若 RBAC 給太大，之後會把 least privilege 邊界做壞
- 若直接做 Helm，現在的 deployment contract 還不夠穩，模板容易反覆重寫

## Implementation Handoff

下一步的 implementation plan 只需要處理：

- `deploy/openclaw/` 目錄建立
- manifests 檔案內容
- README
- 最小驗證方式

先不要同時做 Helm chart、Ingress、PVC 或 ArgoCD。

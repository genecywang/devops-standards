# OpenClaw Plain Manifests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 repo 內建立 `deploy/openclaw/` 的最小 plain manifests 骨架，讓目前的 `OpenClaw` runtime 有可 `kubectl apply -f` 的 Kubernetes deployment 起點。

**Architecture:** 採用 plain manifests directory，將 namespace、RBAC、ConfigMap、Deployment、Service、NetworkPolicy 與 PDB 拆成獨立檔案，維持 stateless `Deployment + ClusterIP Service` 形態。README 只描述最小 apply 與替換 image 的使用方式，不引入 Helm、PVC 或 Ingress。

**Tech Stack:** Kubernetes YAML manifests、`kubectl apply -f`、repo-local deployment docs

---

## File Structure

- Create: `deploy/openclaw/README.md`
- Create: `deploy/openclaw/namespace.yaml`
- Create: `deploy/openclaw/serviceaccount.yaml`
- Create: `deploy/openclaw/role.yaml`
- Create: `deploy/openclaw/rolebinding.yaml`
- Create: `deploy/openclaw/configmap.yaml`
- Create: `deploy/openclaw/deployment.yaml`
- Create: `deploy/openclaw/service.yaml`
- Create: `deploy/openclaw/networkpolicy.yaml`
- Create: `deploy/openclaw/pdb.yaml`

### Task 1: Create Deployment Directory and Namespace Baseline

**Files:**
- Create: `deploy/openclaw/README.md`
- Create: `deploy/openclaw/namespace.yaml`

- [ ] **Step 1: Write the failing existence check**

Run: `test -f deploy/openclaw/README.md && test -f deploy/openclaw/namespace.yaml`

Expected: FAIL，因為 `deploy/openclaw/` 尚未存在。

- [ ] **Step 2: Create the minimal namespace manifest**

在 `deploy/openclaw/namespace.yaml` 建立：

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: openclaw-system
  labels:
    app.kubernetes.io/name: openclaw
    app.kubernetes.io/component: runtime
```

- [ ] **Step 3: Create the initial README**

在 `deploy/openclaw/README.md` 建立：

```md
# OpenClaw Plain Manifests

這裡放的是 `OpenClaw` 的最小 Kubernetes plain manifests 骨架。

## Apply

```bash
kubectl apply -f deploy/openclaw/
```

## Notes

- 這一版使用 `Deployment`，不是 `StatefulSet`
- 這一版不包含 `PVC`、`Ingress`、`HPA`
- 部署前請先替換 `deployment.yaml` 內的 image
```

- [ ] **Step 4: Re-run the existence check**

Run: `test -f deploy/openclaw/README.md && test -f deploy/openclaw/namespace.yaml`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy/openclaw/README.md deploy/openclaw/namespace.yaml
git commit -m "feat: add openclaw deployment namespace baseline"
```

### Task 2: Add ServiceAccount and RBAC

**Files:**
- Create: `deploy/openclaw/serviceaccount.yaml`
- Create: `deploy/openclaw/role.yaml`
- Create: `deploy/openclaw/rolebinding.yaml`

- [ ] **Step 1: Write the failing content check**

Run: `grep -q "pods/status" deploy/openclaw/role.yaml`

Expected: FAIL，因為 RBAC manifest 尚未存在。

- [ ] **Step 2: Create the ServiceAccount**

在 `deploy/openclaw/serviceaccount.yaml` 建立：

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: openclaw-runtime
  namespace: openclaw-system
  annotations:
    eks.amazonaws.com/role-arn: ""
```

- [ ] **Step 3: Create the Role**

在 `deploy/openclaw/role.yaml` 建立：

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: openclaw-runtime-reader
  namespace: openclaw-system
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/status", "events"]
    verbs: ["get", "list", "watch"]
```

- [ ] **Step 4: Create the RoleBinding**

在 `deploy/openclaw/rolebinding.yaml` 建立：

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: openclaw-runtime-reader
  namespace: openclaw-system
subjects:
  - kind: ServiceAccount
    name: openclaw-runtime
    namespace: openclaw-system
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: openclaw-runtime-reader
```

- [ ] **Step 5: Re-run the content check**

Run: `grep -q "pods/status" deploy/openclaw/role.yaml`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add deploy/openclaw/serviceaccount.yaml deploy/openclaw/role.yaml deploy/openclaw/rolebinding.yaml
git commit -m "feat: add openclaw runtime rbac manifests"
```

### Task 3: Add Runtime Config and Service Wiring

**Files:**
- Create: `deploy/openclaw/configmap.yaml`
- Create: `deploy/openclaw/service.yaml`

- [ ] **Step 1: Write the failing content checks**

Run: `grep -q "OPENCLAW_PROVIDER_MODE" deploy/openclaw/configmap.yaml`

Expected: FAIL，因為 ConfigMap 尚未存在。

Run: `grep -q "ClusterIP" deploy/openclaw/service.yaml`

Expected: FAIL，因為 Service manifest 尚未存在。

- [ ] **Step 2: Create the ConfigMap**

在 `deploy/openclaw/configmap.yaml` 建立：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: openclaw-runtime-config
  namespace: openclaw-system
data:
  OPENCLAW_PROVIDER_MODE: "real"
  OPENCLAW_ALLOWED_CLUSTERS: "staging-main"
  OPENCLAW_ALLOWED_NAMESPACES: "payments"
  OPENCLAW_LOG_LEVEL: "INFO"
```

- [ ] **Step 3: Create the Service**

在 `deploy/openclaw/service.yaml` 建立：

```yaml
apiVersion: v1
kind: Service
metadata:
  name: openclaw-runtime
  namespace: openclaw-system
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: openclaw
    app.kubernetes.io/component: runtime
  ports:
    - name: http
      port: 8080
      targetPort: http
```

- [ ] **Step 4: Re-run the content checks**

Run: `grep -q "OPENCLAW_PROVIDER_MODE" deploy/openclaw/configmap.yaml`

Expected: PASS

Run: `grep -q "ClusterIP" deploy/openclaw/service.yaml`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy/openclaw/configmap.yaml deploy/openclaw/service.yaml
git commit -m "feat: add openclaw runtime config and service manifests"
```

### Task 4: Add Deployment Manifest

**Files:**
- Create: `deploy/openclaw/deployment.yaml`

- [ ] **Step 1: Write the failing content checks**

Run: `grep -q "ghcr.io/example/openclaw-foundation:dev" deploy/openclaw/deployment.yaml`

Expected: FAIL，因為 Deployment manifest 尚未存在。

- [ ] **Step 2: Create the Deployment**

在 `deploy/openclaw/deployment.yaml` 建立：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: openclaw-runtime
  namespace: openclaw-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: openclaw
      app.kubernetes.io/component: runtime
  template:
    metadata:
      labels:
        app.kubernetes.io/name: openclaw
        app.kubernetes.io/component: runtime
    spec:
      serviceAccountName: openclaw-runtime
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: openclaw-runtime
          image: ghcr.io/example/openclaw-foundation:dev
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
          envFrom:
            - configMapRef:
                name: openclaw-runtime-config
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            tcpSocket:
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            tcpSocket:
              port: http
            initialDelaySeconds: 15
            periodSeconds: 20
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
```

- [ ] **Step 3: Re-run the content check**

Run: `grep -q "ghcr.io/example/openclaw-foundation:dev" deploy/openclaw/deployment.yaml`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add deploy/openclaw/deployment.yaml
git commit -m "feat: add openclaw runtime deployment manifest"
```

### Task 5: Add NetworkPolicy and PodDisruptionBudget

**Files:**
- Create: `deploy/openclaw/networkpolicy.yaml`
- Create: `deploy/openclaw/pdb.yaml`

- [ ] **Step 1: Write the failing content checks**

Run: `grep -q "kind: NetworkPolicy" deploy/openclaw/networkpolicy.yaml`

Expected: FAIL，因為 NetworkPolicy 尚未存在。

Run: `grep -q "kind: PodDisruptionBudget" deploy/openclaw/pdb.yaml`

Expected: FAIL，因為 PDB 尚未存在。

- [ ] **Step 2: Create the NetworkPolicy**

在 `deploy/openclaw/networkpolicy.yaml` 建立：

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: openclaw-runtime
  namespace: openclaw-system
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: openclaw
      app.kubernetes.io/component: runtime
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: openclaw-system
  egress:
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

- [ ] **Step 3: Create the PDB**

在 `deploy/openclaw/pdb.yaml` 建立：

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: openclaw-runtime
  namespace: openclaw-system
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: openclaw
      app.kubernetes.io/component: runtime
```

- [ ] **Step 4: Re-run the content checks**

Run: `grep -q "kind: NetworkPolicy" deploy/openclaw/networkpolicy.yaml`

Expected: PASS

Run: `grep -q "kind: PodDisruptionBudget" deploy/openclaw/pdb.yaml`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy/openclaw/networkpolicy.yaml deploy/openclaw/pdb.yaml
git commit -m "feat: add openclaw network policy and pdb manifests"
```

### Task 6: Finalize README and Verify Manifests Set

**Files:**
- Modify: `deploy/openclaw/README.md`

- [ ] **Step 1: Write the failing README completeness check**

Run: `grep -q "Deployment" deploy/openclaw/README.md && grep -q "PVC" deploy/openclaw/README.md && grep -q "kubectl apply -f deploy/openclaw/" deploy/openclaw/README.md`

Expected: FAIL，如果 README 還沒完整說明 stateless baseline。

- [ ] **Step 2: Expand the README**

將 `deploy/openclaw/README.md` 更新為：

```md
# OpenClaw Plain Manifests

這裡放的是 `OpenClaw` 的最小 Kubernetes plain manifests 骨架。

## Included Resources

- `Namespace`
- `ServiceAccount`
- `Role`
- `RoleBinding`
- `ConfigMap`
- `Deployment`
- `Service`
- `NetworkPolicy`
- `PodDisruptionBudget`

## Apply

```bash
kubectl apply -f deploy/openclaw/
```

## Notes

- 這一版使用 `Deployment`，不是 `StatefulSet`
- 這一版不包含 `PVC`、`Ingress`、`HPA`
- 部署前請先替換 `deployment.yaml` 內的 image
- 這一版是 stateless runtime baseline，外部狀態需另外處理
```

- [ ] **Step 3: Re-run the README completeness check**

Run: `grep -q "Deployment" deploy/openclaw/README.md && grep -q "PVC" deploy/openclaw/README.md && grep -q "kubectl apply -f deploy/openclaw/" deploy/openclaw/README.md`

Expected: PASS

- [ ] **Step 4: Run the final file-set verification**

Run: `test -f deploy/openclaw/namespace.yaml && test -f deploy/openclaw/serviceaccount.yaml && test -f deploy/openclaw/role.yaml && test -f deploy/openclaw/rolebinding.yaml && test -f deploy/openclaw/configmap.yaml && test -f deploy/openclaw/deployment.yaml && test -f deploy/openclaw/service.yaml && test -f deploy/openclaw/networkpolicy.yaml && test -f deploy/openclaw/pdb.yaml && test -f deploy/openclaw/README.md`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy/openclaw/README.md deploy/openclaw/namespace.yaml deploy/openclaw/serviceaccount.yaml deploy/openclaw/role.yaml deploy/openclaw/rolebinding.yaml deploy/openclaw/configmap.yaml deploy/openclaw/deployment.yaml deploy/openclaw/service.yaml deploy/openclaw/networkpolicy.yaml deploy/openclaw/pdb.yaml
git commit -m "feat: add openclaw plain kubernetes manifests"
```

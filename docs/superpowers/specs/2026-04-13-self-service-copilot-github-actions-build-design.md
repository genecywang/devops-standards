# Self-Service Copilot GitHub Actions Build Design

**Date:** 2026-04-13
**Scope:** GitHub Actions image CI for `self_service_copilot`
**Status:** Proposed

## Context

`self_service_copilot` 已有可部署的 Dockerfile 與 Helm chart，但目前缺少自動化 image build 流程。

短期目標是先把 image build 與 push 自動化，讓手動 deploy 時有穩定可引用的 image tag。CD 仍維持手動，不在這輪 scope 內。

## Goals

- 在 GitHub Actions 自動執行 `self_service_copilot` 的測試與 image build
- 在 `main` push 與 manual dispatch 時，自動 push image 到 `GHCR`
- 產出穩定可部署的 tag：
  - `sha-<shortsha>`
  - `latest`（僅 `main`）
- 保持未來切換到 `ECR` 的空間，不把 workflow 過度綁死在 `GHCR`

## Non-Goals

- 自動 `helm upgrade` / `helm install`
- ArgoCD / Jenkins / release orchestration
- SemVer release tagging
- Multi-arch image build
- SBOM / image signing / vulnerability scanning

---

## 1. Workflow 邊界

新增單一 workflow：

`/.github/workflows/self-service-copilot-image.yml`

責任只包含：

- `pytest`
- `docker build`
- `GHCR login`
- `docker push`

不包含：

- cluster deploy
- Helm release
- Secret 建立

---

## 2. Trigger 策略

### `pull_request`

PR 時只做驗證，不 push image。

條件：

- path filter 命中以下路徑才觸發：
  - `self_service_copilot/**`
  - `openclaw_foundation/**`
  - `.github/workflows/self-service-copilot-image.yml`

PR 驗證內容：

- install packages
- run pytest
- build Docker image

### `push` on `main`

`main` push 時做完整流程：

- install packages
- run pytest
- build Docker image
- login `GHCR`
- push image

### `workflow_dispatch`

保留手動觸發，方便重建 image 或補推 tag。

這一輪不加自訂 input，保持最小 workflow。

---

## 3. Registry 與 Tag 策略

這輪實際目標 registry 是 `GHCR`，但 workflow 設計應盡量保持 registry-agnostic。

image 名稱格式：

`ghcr.io/<owner>/self-service-copilot`

tag 策略：

- `sha-<shortsha>`：所有 push / manual build 都產生
- `latest`：只有 `main` push 時產生

這樣手動 deploy 時可選：

- pin 版本：`sha-*`
- 快速驗證：`latest`

### 未來切 `ECR`

切到 `ECR` 時應只需調整：

- registry login step
- image repository base

測試、build、tag 邏輯不需重寫。

---

## 4. Workflow 結構

建議拆成兩個 jobs：

### `test`

責任：

- checkout repo
- setup Python 3.11
- install `openclaw_foundation`
- install `self_service_copilot`
- run pytest

測試指令：

```bash
python -m pip install --upgrade pip
python -m pip install ./openclaw_foundation ./self_service_copilot
python -m pytest openclaw_foundation/tests self_service_copilot/tests -q
```

### `image`

依賴：`needs: test`

責任：

- checkout repo
- setup Docker Buildx
- login `GHCR`（僅 push / manual）
- build image from repo root
- on `main` / manual push tags to `GHCR`

build command：

```bash
docker build -f self_service_copilot/Dockerfile -t <image-ref> .
```

### 為什麼不用三個 jobs

不另外拆 `push` job，原因是這輪不需要：

- artifact handoff
- matrix build
- multi-registry push

兩個 jobs 足夠，也比較容易維護。

---

## 5. GitHub Permissions 與 Credentials

workflow 需要：

```yaml
permissions:
  contents: read
  packages: write
```

`GHCR` login 使用：

- `github.actor`
- `secrets.GITHUB_TOKEN`

這樣可以避免先引入額外 PAT。

前提是 repo / org 對 `GITHUB_TOKEN` 推 `GHCR` 的權限已允許。

若未來組織政策不允許，再改為專用 secret token。

---

## 6. Path Filter 原則

只要這些路徑有變更，就觸發 workflow：

- `self_service_copilot/**`
- `openclaw_foundation/**`
- `.github/workflows/self-service-copilot-image.yml`

這輪刻意不包含：

- `deploy/charts/self-service-copilot/**`

理由：

- chart 變更本身不需要重建 image
- 避免每次只改 Helm values / template 也浪費 CI build 時間

---

## 7. Failure Model

### 測試失敗

`test` job fail，`image` job 不執行。

### Docker build 失敗

PR 直接顯示 fail，不 push。

### `GHCR` login / push 失敗

只影響 `main` / manual 的 push path，不影響 PR 驗證設計。

### Tag 衝突

`sha-<shortsha>` 天然避免衝突；`latest` 允許覆蓋。

---

## 8. Manual Deploy 合約

這條 workflow 的產物是 image，不是 release。

部署仍維持手動，例如：

```bash
helm upgrade --install staging-copilot deploy/charts/self-service-copilot/ \
  --namespace <namespace> \
  --set image.repository=ghcr.io/<owner>/self-service-copilot \
  --set image.tag=sha-<shortsha>
```

這確保：

- CI 責任是 build artifact
- deploy 決策仍由人控制

---

## 9. File Changes

### 新增

- `.github/workflows/self-service-copilot-image.yml`

### 可選補充

- `self_service_copilot/README.md`
  - 補一段 image build / tag 說明

這輪不修改 application code。

---

## 10. Trade-offs

### 選擇 GitHub Actions，而不是 Jenkins

優點：

- 對 `GHCR` 最順手
- setup 成本低
- repo-local，維護簡單

缺點：

- 與現有 Jenkins / ArgoCD 生態未整合
- 未來若公司要求集中式 CI，可能需要搬遷

### 選擇 build-only，不做 deploy

優點：

- scope 小
- 不碰 cluster 寫入
- 手動 deploy 風險較低

缺點：

- 仍需人工執行 release

### 選擇 PR build 不 push

優點：

- 不污染 registry
- 仍可驗證 Dockerfile 與 repo buildability

缺點：

- PR 無法直接拿到 registry image 做 downstream 測試

---

## 11. Recommended Next Step

這份 spec 對應的 implementation plan 應拆成：

1. workflow scaffold
2. pytest job
3. Docker build job
4. GHCR push 條件邏輯
5. README 補充與驗證

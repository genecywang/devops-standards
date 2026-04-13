# Self-Service Copilot GitHub Actions Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 `self_service_copilot` 建立 GitHub Actions build-only CI：PR 驗證測試與 Docker build，`main` / manual 才 push image 到 `GHCR`。

**Architecture:** 新增單一 workflow `.github/workflows/self-service-copilot-image.yml`。`test` job 先安裝兩個 Python package 並跑 pytest；`image` job 依賴 `test`，PR 只 build、不 push，`main` push 與 `workflow_dispatch` 才 login `GHCR` 並推 `sha-*` 與 `latest` tag。

**Tech Stack:** GitHub Actions, Docker Buildx, GHCR, Python 3.11, pytest

---

## File Structure

| 狀態 | 路徑 | 責任 |
|------|------|------|
| 新增 | `.github/workflows/self-service-copilot-image.yml` | image CI workflow |
| 修改 | `self_service_copilot/README.md` | 補 CI image tag / manual deploy 說明 |

---

## Task 1: Workflow scaffold and trigger policy

**Files:**
- Create: `.github/workflows/self-service-copilot-image.yml`

- [ ] **Step 1: 建立 workflow 檔案骨架**

建立以下內容：

```yaml
name: self-service-copilot-image

on:
  pull_request:
    paths:
      - "self_service_copilot/**"
      - "openclaw_foundation/**"
      - ".github/workflows/self-service-copilot-image.yml"
  push:
    branches:
      - main
    paths:
      - "self_service_copilot/**"
      - "openclaw_foundation/**"
      - ".github/workflows/self-service-copilot-image.yml"
  workflow_dispatch:

permissions:
  contents: read
  packages: write

env:
  IMAGE_NAME: ghcr.io/${{ github.repository_owner }}/self-service-copilot

jobs: {}
```

- [ ] **Step 2: 目視檢查 trigger 是否符合 spec**

確認：

- PR 會觸發
- `main` push 會觸發
- `workflow_dispatch` 可手動觸發
- path filter 不包含 `deploy/charts/self-service-copilot/**`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/self-service-copilot-image.yml
git commit -m "feat: scaffold github actions workflow for self-service-copilot image"
```

---

## Task 2: Add pytest job

**Files:**
- Modify: `.github/workflows/self-service-copilot-image.yml`

- [ ] **Step 1: 在 workflow 補上 `test` job**

在 `jobs:` 下加入：

```yaml
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Upgrade pip
        run: python -m pip install --upgrade pip

      - name: Install packages
        run: python -m pip install ./openclaw_foundation ./self_service_copilot

      - name: Run pytest
        run: python -m pytest openclaw_foundation/tests self_service_copilot/tests -q
```

- [ ] **Step 2: 本機用同等指令驗證測試命令**

在 repo root 執行：

```bash
python3 -m pip install ./openclaw_foundation ./self_service_copilot
python3 -m pytest openclaw_foundation/tests self_service_copilot/tests -q
```

Expected:

- 安裝成功
- pytest 全綠

若本機 Python 環境不適合安裝，至少用既有 venv 驗證：

```bash
openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests -q
cd self_service_copilot && .venv/bin/python -m pytest tests -q
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/self-service-copilot-image.yml
git commit -m "feat: add pytest job to self-service-copilot image workflow"
```

---

## Task 3: Add Docker build job for PR validation

**Files:**
- Modify: `.github/workflows/self-service-copilot-image.yml`

- [ ] **Step 1: 在 workflow 補上 `image` job 骨架**

在 `test` job 後加入：

```yaml
  image:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Derive short SHA
        id: meta
        run: echo "short_sha=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

      - name: Build image
        run: |
          docker build \
            -f self_service_copilot/Dockerfile \
            -t "${IMAGE_NAME}:sha-${{ steps.meta.outputs.short_sha }}" \
            .
```

- [ ] **Step 2: 本機驗證 Docker build 指令**

在 repo root 執行：

```bash
docker build -f self_service_copilot/Dockerfile -t self-service-copilot:local .
```

Expected:

- image build 成功

若本機無 Docker，至少驗證指令可用：

```bash
docker build --help > /dev/null && echo "docker available" || echo "docker not available"
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/self-service-copilot-image.yml
git commit -m "feat: add docker build job to self-service-copilot image workflow"
```

---

## Task 4: Add GHCR login and conditional push

**Files:**
- Modify: `.github/workflows/self-service-copilot-image.yml`

- [ ] **Step 1: 在 `image` job 加入 push 條件與 login**

在 `Build image` 後加入：

```yaml
      - name: Log in to GHCR
        if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Tag latest for main
        if: github.ref == 'refs/heads/main'
        run: |
          docker tag \
            "${IMAGE_NAME}:sha-${{ steps.meta.outputs.short_sha }}" \
            "${IMAGE_NAME}:latest"

      - name: Push sha tag
        if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'
        run: docker push "${IMAGE_NAME}:sha-${{ steps.meta.outputs.short_sha }}"

      - name: Push latest tag
        if: github.ref == 'refs/heads/main'
        run: docker push "${IMAGE_NAME}:latest"
```

- [ ] **Step 2: 檢查條件邏輯**

確認：

- PR 不會 login / push
- `main` push 會推：
  - `sha-*`
  - `latest`
- `workflow_dispatch` 只推：
  - `sha-*`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/self-service-copilot-image.yml
git commit -m "feat: add ghcr push logic to self-service-copilot image workflow"
```

---

## Task 5: README handoff and manual deploy guidance

**Files:**
- Modify: `self_service_copilot/README.md`

- [ ] **Step 1: 在 README 增加 CI image 說明**

在 README 末尾補上：

```md
## Image CI

GitHub Actions workflow:

- PR：run pytest + docker build，不 push image
- `main` push：run pytest + docker build + push to `GHCR`
- `workflow_dispatch`：手動 build + push `sha-*` tag

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
```

- [ ] **Step 2: Commit**

```bash
git add self_service_copilot/README.md
git commit -m "docs: add image ci and manual deploy guidance"
```

---

## Task 6: Verify workflow and close the loop

**Files:**
- Modify: `.github/workflows/self-service-copilot-image.yml`
- Modify: `self_service_copilot/README.md`

- [ ] **Step 1: 檢查 workflow YAML**

執行：

```bash
sed -n '1,260p' .github/workflows/self-service-copilot-image.yml
```

確認：

- 有 `pull_request`, `push`, `workflow_dispatch`
- `permissions.contents = read`
- `permissions.packages = write`
- `test` 與 `image` 兩個 jobs 都存在

- [ ] **Step 2: 再次驗證現有測試**

執行：

```bash
openclaw_foundation/.venv/bin/python -m pytest openclaw_foundation/tests -q
cd self_service_copilot && .venv/bin/python -m pytest tests -q
```

Expected:

- foundation tests 全綠
- copilot tests 全綠

- [ ] **Step 3: 可選驗證 Helm 不受影響**

執行：

```bash
helm lint deploy/charts/self-service-copilot/
```

Expected:

- `1 chart(s) linted, 0 chart(s) failed`

- [ ] **Step 4: Final commit**

```bash
git add .github/workflows/self-service-copilot-image.yml self_service_copilot/README.md
git commit -m "feat: add github actions image ci for self-service-copilot"
```

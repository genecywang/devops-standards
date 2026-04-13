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

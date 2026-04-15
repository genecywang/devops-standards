      - alert: HttpBlackboxProbeFailed
        expr: probe_success{job="blackbox-h2s-backend_api"} == 0
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: Host unusual network throughput out (instance {{ $labels.instance }})
          description: "Http Probe down : {{ $labels }}"
          ClusterName: H2-EKS-DEV-STG

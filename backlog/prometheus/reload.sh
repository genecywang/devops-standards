#!/bin/bash
curl -XPOST -vvv http://prometheus-service.monitoring.svc.cluster.local:9090/-/reload

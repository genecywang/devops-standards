{{- define "self-service-copilot.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "self-service-copilot.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "self-service-copilot.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "self-service-copilot.labels" -}}
helm.sh/chart: {{ include "self-service-copilot.chart" . }}
app.kubernetes.io/name: {{ include "self-service-copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "self-service-copilot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "self-service-copilot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

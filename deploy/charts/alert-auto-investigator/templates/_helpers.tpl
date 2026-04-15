{{- define "alert-auto-investigator.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "alert-auto-investigator.fullname" -}}
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

{{- define "alert-auto-investigator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "alert-auto-investigator.labels" -}}
helm.sh/chart: {{ include "alert-auto-investigator.chart" . }}
app.kubernetes.io/name: {{ include "alert-auto-investigator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "alert-auto-investigator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "alert-auto-investigator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

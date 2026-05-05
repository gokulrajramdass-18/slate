{{/*
Expand the name of the chart.
*/}}
{{- define "slate.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "slate.fullname" -}}
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

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "slate.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "slate.labels" -}}
helm.sh/chart: {{ include "slate.chart" . }}
{{ include "slate.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "slate.selectorLabels" -}}
app.kubernetes.io/name: {{ include "slate.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend labels
*/}}
{{- define "slate.backend.labels" -}}
{{ include "slate.labels" . }}
app: slate
component: backend
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "slate.frontend.labels" -}}
{{ include "slate.labels" . }}
app: slate
component: frontend
{{- end }}

{{/*
AppRouter labels
*/}}
{{- define "slate.approuter.labels" -}}
{{ include "slate.labels" . }}
app: slate
component: approuter
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "slate.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "slate.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image registry
*/}}
{{- define "slate.imageRegistry" -}}
{{- if .Values.global.imageRegistry }}
{{- printf "%s/" .Values.global.imageRegistry }}
{{- end }}
{{- end }}

{{/*
Backend image
*/}}
{{- define "slate.backend.image" -}}
{{- printf "%s%s:%s" (include "slate.imageRegistry" .) .Values.backend.image.repository .Values.backend.image.tag }}
{{- end }}

{{/*
Frontend image
*/}}
{{- define "slate.frontend.image" -}}
{{- printf "%s%s:%s" (include "slate.imageRegistry" .) .Values.frontend.image.repository .Values.frontend.image.tag }}
{{- end }}

{{/*
AppRouter image
*/}}
{{- define "slate.approuter.image" -}}
{{- printf "%s:%s" .Values.approuter.image.repository .Values.approuter.image.tag }}
{{- end }}

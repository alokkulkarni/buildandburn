{{/* Generate basic labels */}}
{{- define "test-app.labels" -}}
app.kubernetes.io/name: {{ .Release.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* Generate selector labels */}}
{{- define "test-app.selectorLabels" -}}
app: {{ .Release.Name }}-nginx
{{- end -}} 
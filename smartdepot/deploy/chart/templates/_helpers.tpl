{{- define "pcai.name" -}}
{{- .Release.Name | trunc 53 | trimSuffix "-" -}}
{{- end -}}
{{- define "pcai.labels" -}}
app.kubernetes.io/name: pcai-app
app.kubernetes.io/instance: {{ .Release.Name | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
hpe-ezua/type: vendor-service
{{- end -}}
{{- define "pcai.selector" -}}
app.kubernetes.io/name: pcai-app
app.kubernetes.io/instance: {{ .Release.Name | quote }}
{{- end -}}
{{- define "pcai.validate" -}}
{{- required "Set image.repository using Configure PCAI.cmd" .Values.image.repository | quote | trunc 0 -}}
{{- required "Set ezua.virtualService.endpoint using Configure PCAI.cmd" .Values.ezua.virtualService.endpoint | quote | trunc 0 -}}
{{- required "Set auth.issuerURL using Configure PCAI.cmd" .Values.auth.issuerURL | quote | trunc 0 -}}
{{- required "Set auth.clientID using Configure PCAI.cmd" .Values.auth.clientID | quote | trunc 0 -}}
{{- required "Set auth.existingSecret; credentials do not belong in chart values" .Values.auth.existingSecret | quote | trunc 0 -}}
{{- required "Set litellm.existingSecret; credentials do not belong in chart values" .Values.litellm.existingSecret | quote | trunc 0 -}}
{{- if not .Values.auth.allowedGroups -}}{{ fail "Set at least one auth.allowedGroups entry" }}{{- end -}}
{{- if and (eq .Values.routing.mode "ingress") (not .Values.ingress.tlsSecretName) -}}{{ fail "Ingress mode requires ingress.tlsSecretName" }}{{- end -}}
{{- end -}}

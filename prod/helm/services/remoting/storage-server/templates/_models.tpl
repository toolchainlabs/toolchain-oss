# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

{{/* storage-server config for sharded Redis backend setup */}}
{{- define "storage-server.redis-sharded-backends" -}}
{{- $numConnections := .Values.redis.num_connections -}}
redis_backends:
  {{- range $shard_key, $shard_host := .Values.redis.shards_config }}
  {{ quote $shard_key }}:
    address: {{ $shard_host }}:6379
    num_connections: {{ $numConnections }}
  {{- end -}}
{{- end }}


{{/* Sharded direct redis snippet for use as CAS storage */}}
{{- define "storage-server.cas-sharded-direct" -}}
sharded:
  num_replicas: {{ .Values.redis.num_replicas }}
  shards:
    {{- range $shard_key, $shard_host := .Values.redis.shards_config}}
    - shard_key: {{ quote $shard_key }}
      storage:
        redis_direct:
          backend: {{ quote $shard_key }}
          prefix: "cd-"
    {{- end}}
{{- end }}


{{/* Sharded direct redis snippet for use as AC storage */}}
{{- define "storage-server.ac-sharded-direct" -}}
# The Action Cache should never have large blobs. Only `ActionResult` protos are stored in the AC (and
# storage-server strips any inline stdout/stderr contents from an ActionResult before storing it.)
sharded:
  num_replicas: {{ .Values.redis.num_replicas }}
  shards:
    {{- range $shard_key, $shard_host := .Values.redis.shards_config}}
    - shard_key: {{ quote $shard_key }}
      storage:
        redis_direct:
          backend: {{ quote $shard_key }}
          prefix: "ad-"
    {{- end}}
{{- end }}


{{/* Sharded storage config for small blobs, large blobs in EFS. No Amberflo (suitable for dev). */}}
{{- define "storage-server.model.sharded-redis" -}}
{{- include "storage-server.redis-sharded-backends" . }}

cas:
  size_split:
    size: {{ .Values.sizeSplitThreshold }}
    smaller: {{- include "storage-server.cas-sharded-direct" . | nindent 6 }}
    larger:
      local:
        base_path: {{ .Values.storage.base_path }}

action_cache: {{- include "storage-server.ac-sharded-direct" . | nindent 2 }}

{{- end}}

{{/* Sharded and fast/slow for small blobs, large blobs in EFS (with Amberflo). */}}
{{- define "storage-server.model.sharded-redis-fast-slow" -}}
{{- include "storage-server.redis-sharded-backends" . }}

cas:
  metered:
    size_split:
      size: {{ .Values.sizeSplitThreshold }}
      smaller:
        read_cache:
          fast: {{- include "storage-server.cas-sharded-direct" . | nindent 12 }}
          slow:
            local:
              base_path: {{ .Values.storage.base_path }}
      larger:
        local:
          base_path: {{ .Values.storage.base_path }}

action_cache:
  metered: {{- include "storage-server.ac-sharded-direct" . | nindent 4 }}
{{- end}}

{{/* Returns the string "true" if EFS is enabled. */}}
{{- define "storage-server.isEFSEnabledForModel" -}}
{{- has . (list "sharded-redis" "sharded-redis-fast-slow-darklaunch" "sharded-redis-fast-slow") -}}
{{- end }}

{{/* Returns the string "true" if Amberflo support is enabled. */}}
{{- define "storage-server.isAmberfloEnabledForModel" -}}
{{- has . (list "sharded-redis-fast-slow-darklaunch" "sharded-redis-fast-slow") -}}
{{- end }}

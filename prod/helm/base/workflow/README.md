# Using templates from a subchart

This chart exists only to provide named templates for other charts to instantiate.
It has no concrete resources itself (Helm doesn't consider files starting with a _ to represent resources).
Therefore this chart is never installed directly, and its templates are only processed when included in a
dependent chart's template, and in the context of that chart's values.

In that context, this chart's values appear nested under the 'workflow' key. But we want this template
to reference values without that nesting.  So the following incantation, at the top of each template,
merges the values under that key into the top level .Values, with the latter taking precedence:

```yaml
{{- $workflow := dict "Values" .Values.workflow -}}
{{- $noWorkflow := omit .Values "workflow" -}}
{{- $overrides := dict "Values" $noWorkflow -}}
{{- $noValues := omit . "Values" -}}
{{- with merge $noValues $overrides $workflow -}}
```

See <https://medium.com/devopslinks/dry-helm-charts-for-micro-services-db3a1d6ecb80>.

Don't be confused by discussion in the Helm documentation of how a dependent ("parent" in their terminology) chart can override the values of a dependency ("subchart" - they freely and confusingly mix dependency and inheritance terminology): that's relevant when directly installing the dependency itself, which we never do with this chart (again, we only use this chart as a repository of named templates for other charts to re-use).

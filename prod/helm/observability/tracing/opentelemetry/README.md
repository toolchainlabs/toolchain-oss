# OpenTelemetry Collector

This chart installs the OpenTelemetry Collector which receives distributed tracing spans in various formats
(including Jaeger, Zipkin, and OTLP) and then processes and exports them elsewhere. This chart
currently exports spans to [Honeycomb](https://honeycomb.io) via OTLP.

## Secret

The secret for the Honeycomb API key must be created in AWS Secrets Manager before installing this chart. Run
the following command, replacing API_KEY with the API Key obtained from the Honeycomb Team Settings page.

```shell
aws secretsmanager create-secret \
  --name="honeycomb/api-key" \
  --description="API Key for Honeycomb service" \
  --secret-string="API_KEY"
```

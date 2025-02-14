# Web Hooks Services

A service that accepts and processes web hooks from external services.

## Dev flow

To test running locally or in k8s dev, you will need to use [ngrok](https://ngrok.com) to route GitHub Webhooks into the process in dev.

Alternatively, you can use fixtures & postman/curl to hit the webhooks API locally.

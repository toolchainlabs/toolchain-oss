# Secrets storage

Secrets, such as database credentials, must be stored securely, yet be accessible
to code that needs them.

We support a few different secrets stores:

- [AWS SecretsManager](https://aws.amazon.com/secrets-manager/)
- [Kubernetes `Secret` API](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes `Secret` Volume](https://kubernetes.io/docs/concepts/configuration/secret/#using-secrets)
- Local secret files (for development only)

The [`SecretsReader/SecretsAccessor`](./secrets_accessor.py)
abstractions allow client code to be ignorant of which secrets store is in use.

Note that Kubernetes mounts secrets as volumes so that pods can consume them without needing to
directly access the control plane via the Kubernetes API. The API is still needed for setting
secret values.

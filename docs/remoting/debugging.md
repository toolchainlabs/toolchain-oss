# Remote Cache Debugging

## Production

### Invoking CLI Tools

The production cache requires an authentication token to gain access. Tools such as
[`casload`](https://github.com/toolchainlabs/remote-api-tools), [`smoketest`](https://github.com/toolchainlabs/remote-api-tools),
or [`fs_util`](https://github.com/pantsbuild/pants/tree/main/src/rust/engine/fs/fs_util) will need to be
invoked with an applicable token. The token is dynamic and will need to be obtained from the `with_cas_token` tool.

Build the `with_cas_token` PEX: `./pants package src/python/toolchain/remoting:with_cas_token`

Put `./dist/src.python.toolchain.remoting/with_cas_token.pex` somewhere on your PATH or just invoke directly. (The
examples below assume that you placed it somewhere on your PATH.)

When using in ***DEV*** make sure you port forward service router and remote cache proxy server to the local machine by running (in diffrerent termianl windows/sessions):

```shell
./src/sh/kubernetes/port_forward.sh servicerouter
```

and

```shell
kubectl port-forward --context=dev-e1-1 svc/remoting-proxy-server 8980:8980
```

Examples for each tool:

- `casload`: `with_cas_token.pex ./casload PROGRAM...`
  (where `PROGRAM...` is replaced with your load testing directives)
- `smoketest`: `with_cas_token.pex ./smoketest`

The tool defaults to use the production environment, you can use dev by passing the `--dev` flag or hit staing env (in prod) using `--staging`.
For example: `with_cas_token.pex --dev ./smoketest` or `with_cas_token.pex --staging ./casload generate:5:1000:10000 read:5:1`

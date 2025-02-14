# servicerouter

A service that serves two purposes:

- Serve the frontend.
- Proxies requests to various backend services.

For more context, see the service routing in [`urls.py`](./urls.py) and [Frontend app README](../../../node/toolchain/frontend/README.md)

Service router is the front end api part for Toolchain web app.
It severs traffic coming into <https://app.toolchain.com>

Service router acts as a proxy and passes request to various backend apis/services (users, buildsense, etc).

Service router [uses a configuration file](./service_routes.json) - (which is still part of the shipped code) to build a list of urls to expose (and pass that info do Django) map them to internal services.

The service router checks for JWT tokens in the headers and will decode them if them and attach them to the request if they are available, is is done via the [JwtAuthMiddleware](../users/jwt/middleware.py).

Service router will pass the decoded authN (user identity, repo and customer id in some cases) and authZ (audience/permission) and validate them (make sure user is active, token is valid, etc..).

Service router, specifically [ServiceRouterRequestMiddleware](./services_router.py) (note that this is NOT a Django middleware),  passes the “decoded” user authN ()and authZ () using a json object encoded into a http header `X-Toolchain-Internal-Auth`.

Downstream services use [InternalServicesMiddleware](../django/auth/middleware.py) that decodes those headers and attach relevant information to the request object.

The various views are then responsible for checking that the supplies permissions and the user are allowed to access a given resource .
This is done via a [DRF permissions](https://www.django-rest-framework.org/api-guide/permissions/) [plugin](../users/jwt/permissions.py) but there are also some views that will implement additional checks either directly or indirectly.

The service router uses the httpx package  to issue downstream request.
Currently, the service doesn't provide robust mitigation against network issues downstream (timeouts, other socket errors) beside having a basic retry  mechanism (implemented by httpx).
This means that transient network errors will cause HTTP 500 errors (and will be reported to sentry).

Ideally, we should be handling those and return HTTP 503 Service Unavailable, with some payload that will tell clients we control (toolchain pants plugin and the SPA/UI) to retry.

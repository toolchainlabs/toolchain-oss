# Users Service

The users service manages our basic objects (users, repos, customers/orgs) and handles auth related objects and workflows.

## Users auth to the Toolchain Web App

We support two 3rd party auth providers: GitHub and bitbucket.
We use an industry standard [oauth 2.0 flow](https://oauth.net/2/) to authenticate users and allow them to access our web app & services.

### Auth flow overview

- Redirect the user to the auth provider.
- User auths with the provider and grants limited access to their account to the Toolchain service. Granting access happens once (unless revoked).
- The provider redirects the user back to Toolchain web app passing a one time code via query parameters, in our backend we exchange this code for an access token.
- We use this access token to access the provider's API and read the user account info (username, full name, emails) and organization memberships.
- Evaluate the user information to figure out if the user is allowed to access Toolchain and update or create the ToolchainUser and UserAuth object in our system.
- If the user is allowed to access Toolchain we will send the user’s browser a refresh token (in a cookie).
- The web app (JS/SPA) will use this refresh token and will exchange it for an access token.
- The web app (JS/SPA) will use this access token to access various APIs to get data and populate the UI.

### Eligibility to access Toolchain web app

Currently by default, 'random' users are not granted access to the Toolchain system.
So unless the mechanism described below determines otherwise, we don't allow users to access our system by default.

There are a few things we check in order to see if a user should be allowed to access Toolchain:

- Org membership - we check if any of the organizations / accounts that the user is associated with has a corresponding *active* customer object in our system, if so the user is granted access. Important note here: organizations/customers can be marked as `allow-access false` (for example the [pantsbuild](https://github.com/pantsbuild) org is marked in this way), and in those cases this check will disregard the membership in those organizations.

- Allow list - we check if any of the user’s validated email address (validated by the auth provider) is in our allow list table, and if so we let the user in. If a customer slug is specified in the allow list record, we will also associate that user with that customer/org.

## JSON Web Tokens (JWT)

We use two types of JWT: Refresh tokens and access token

### Refresh tokens

Refresh tokens are long lived tokens, they are stored by the client that uses them.
We keep track of refresh token we issued in the AllocatedRefreshToken table/model.
There are two client that are currently supported: UI/SPA and Toolchain Pants plugin.

#### UI/SPA Refresh tokens

These tokens are referred in the code as UI tokens.
Upon login we will either provide the user with an exiting active token (non-expired/revoked) or we will issue a new token as there isn't an existing one we can use.

The token is stored in a cookie, (the server sets the cookie and can automatically update it with new tokens as needed i.e. as the refresh token/cookie is about to expire, the server will send an new refresh token via a cookie.

#### Toolchain pants plugin

These tokens are referred in the code as API tokens.
The user must explicitly run a pants command (`./pants auth-acquire`) to get a refresh token from our system.
The plugin will store it on disk (under the relevant repo directory).
The Web app [provides UI](https://app.toolchain.com/tokens/) where the user can see all the refresh tokens allocated for the plugin and revoke active tokens.
This flow will always cause a new token to be issued. We do not reuse/re-send existing tokens.
There is a limit on the number of active tokens.

### Access Tokens

The API the refresh token can be used with is the [AccessTokenRefreshView API](./jwt/views.py) for exchanging it for a short lived access token.
Access tokens are the token that are require to access our api endpoints.

When issuing an access token, we validate the refresh token and the user associated with it.
Both the SPA and the Toolchain pants plugin do not persist the access token and only keep it in memory.

## Permissions (aka audience)

We add permissions to the token based on the user configured permissions and based on permissions requested. There is a single permissions for all the API used by the UI (js/spa) - `AccessTokenAudience.FRONTEND_API`

The Toolchain pants plugin has a more granular permissions model so there are permissions to access buildsense, cache (read only or read write), impersonation permissions (used for CI scenarios)etc…

Each system/view is responsible to check that the provided permissions match the permissions required to access that part of the system/api.
On the python side we use [DRF permissions](https://www.django-rest-framework.org/api-guide/permissions/) [objects](./jwt/permissions.py) in conjunction with an `audience` attribute on our view in order to facilitate those checks.

### Remote Execution permissions

By default we don't give customers remote execution permissions at this time.
In prod, we specify a list of customers/orgs by slugs in the User's API service config via _REMOTE_EXEC_CUSTOMERS_SLUGS_IN_PROD in [resources_resolver.py](../prod/tools/resources_resolver.py) which are allowed to request remote execution permissions (via a the Toolchain Pants  Plugin).

Note that with a current implementation, it is not eough of the customer to be allowed that permissions, a specific user (assoicated with that customer) must also be allowed to request that permissions via the Toolshed UI via the [User Customer Access config UI](https://toolshed.toolchainlabs.com/db/users/admin/users/usercustomeraccessconfig/).

If the customer is not in the allow list and someone request that permissions, it will fail. However if the customer is allowed but the user is not, the operation will *not* fail and will simply returtn a token without the requested permsission (and will log an warning to the user about that).

### Restricted Access Tokens

Restricted access tokens are a special construct that we use for open source projects (currently only pants).
Background: We don't want pull requests (which any github user can create) to have access to repo secrets (since that PR can run any code and leak those secrets). So by default, GitHub doesn't let PR builds access repo secrets.
Note that this is only for pull requests builds.
Branch builds on the other hand do have access to repo secrets to they can use a refresh token stored there (which gets mapped to an environment variable) and use that to acquire an access token and access Toolchain services (remote cache, buildsense).

For PR builds, the toolchain pants plugin will detect that no token is available via an environment variable and will try to request an access token from the Toolchain APIs via a dedicated endpoint (`api/v1/token/restricted/`) which is implemented in `RestrictedAccessTokenView`.
As they payload for that request the plugin uploads a bunch of relevant environment variables.

The server endpoint uses those environment variables in conjunction with data received from GitHub (via webhooks) to validate the PR state and the CI run.
This logic is mostly implemented in the `CIResolveView` which is part of github_integration app (running under the scm-integration/api service).
If this view determines that the CI run is 'legit' it will send back an HTTP 200 and will include some data that was extracted from the github PR (and possibly CI) data.

The logic in `RestrictedAccessTokenView` will make sure they user running the PR is a known toolchain user (otherwise, a token will not be issued) and update table (`RestrictedAccessToken`) to keep some accounting when allocating this token (since we want to limit the number of token we allow a given PR/CI run to have).

To get started with Toolchain, you'll need:

- A GitHub account
- A GitHub organization, with at least one repository that has Pants (version 2.14 or higher) set up

Most of the steps in this setup process require you to hold the [organization owner role](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization#organization-owners) in your GitHub organization. 

As organization owner, you'll need to follow steps in GitHub first, followed by making some changes to your repository's Pants configuration.

Additionally, [each individual user will need to authenticate](#local-development-for-each-user) on each machine they use for local development.

## Connect Toolchain to your GitHub Repositories (organization owner only)

Go to the Toolchain app at <https://app.toolchain.com> and sign in with GitHub.

You will be asked to agree to the Toolchain customer agreement and to authorize the Toolchain GitHub application.

You will then be asked to choose which organization to install the application into.

When you are asked to select whether to install to all repositories or select repositories, choose "Only select repositories", and select the repositories from your organization that use Pants and you want to enable instrumentation and caching for. 

> 🚧 Unpredictable behavior when you select "all repositories"
> 
> Toolchain enforces a limit of 25 repositories per organization.
> 
> If you enable the GitHub application for all repositories in an organization that has more than 25 repositories, only 25 repositories will be enabled. If you inadvertently choose "all repositories" and a repository you care about was missed, please [contact Toolchain support](mailto:support@toolchain.com), and we can free up space by disabling services on other repositories.

[block:image]
{
  "images": [
    {
      "image": [
        "https://files.readme.io/bcb0585-2022-07-07_at_9.18_AM.png",
        "2022-07-07 at 9.18 AM.png",
        622
      ],
      "align": "center",
      "caption": "A screenshot from GitHub, showing options to install the Toolchain Build System to one of several organizations."
    }
  ]
}
[/block]

[block:image]
{
  "images": [
    {
      "image": [
        "https://files.readme.io/3ef4876-2022-07-07_at_9.19_AM.png",
        "2022-07-07 at 9.19 AM.png",
        728
      ],
      "align": "center",
      "caption": "A screenshot from GitHub, showing options for installing and authorizing the Toolchain Build System GitHub application. The \"only select repositories\" option is selected, and a repository named \"example-python\" has been highlighted."
    }
  ]
}
[/block]

When you have successfully authorized the Toolchain app into your repositories, you'll be brought to the repository list screen in Toolchain's dashboard.

[block:image]
{
  "images": [
    {
      "image": [
        "https://files.readme.io/1d16860-2022-07-07_at_10.30_AM.png",
        "2022-07-07 at 10.30 AM.png",
        1029
      ],
      "align": "center",
      "caption": "A screenshot from Toolchain's dashboard, showing an organization with one repository available."
    }
  ]
}
[/block]

> 👍 You've successfully authorized the GitHub application!
> 
> If you've made it here, then you have successfully authorized the GitHub application, and you can now start configuring the Pants installation in your repository to communicate with Toolchain.

## Configure Pants to use Toolchain

The Toolchain plugin enables both our build instrumentation tool, BuildSense, as well as authentication for our remote cache service. Setting these up requires both global configuration -- for both CI and local builds, as well as CI-specific configuration.

> 📘 Pants configuration conventions
> 
> The rest of these steps assume that you have a secondary Pants configuration file for your CI environment, named `pants.ci.toml`, alongside your primary configuration file (which has the default name `pants.toml`). 
> 
> If you do not already have a separate CI configuration file, see the Pants documentation for information on configuring your [CI environment to use additional Pants configuration files](https://www.pantsbuild.org/docs/using-pants-in-ci#configuring-pants-for-ci-pantscitoml-optional).

### Add Toolchain to your Pants configuration

In your `pants.toml` file, add the Toolchain pants plugin to your plugins list, along with some initial configuration in the `[GLOBAL]` section of the file:

```toml
[GLOBAL]  # Add to existing [GLOBAL] section if you have one.

plugins.add = [
  "toolchain.pants.plugin==0.27.0",
]

remote_cache_read = false
remote_cache_write = false
```

Finally, add a `toolchain-setup` block to point the Toolchain plugin at your repository on GitHub -- replace the `organization-name` and `repository-name` with the GitHub organization and repository name respectively:

```toml
[toolchain-setup]
org = "organization-name"
repo = "repository-name"
```

Commit the changes to your `pants.toml` file to your repository.

### Configure Pants to use remote caching in your CI environment:

Follow the [pants guidance](https://www.pantsbuild.org/docs/using-pants-in-ci) on how to configure pants in a CI environment

In your `pants.ci.toml` file, add the following:

```toml
remote_cache_read = true
remote_cache_write = true

[auth]
from_env_var = "TOOLCHAIN_AUTH_TOKEN"
```

Ensure that these changes are committed to your repository.

## Authenticate with Toolchain's Services

Each user should authenticate with Toolchain on every machine where they work in this repository. This will allow each development build to be instrumented by Toolchain. 

Additionally, organization owners will need to create an authentication token so that CI builds can be instrumented, and to enable the remote cache for CI builds.

### Local development for each user

Each user will need to acquire an authentication token for their build traces to be sent to Toolchain for viewing in Buildsense. The Toolchain plugin adds new goals to Pants that allow you to authenticate against Toolchain's services.

Once you have configured the plugin, you can run the following command:

```
./pants auth-acquire
```

On local machines with a web browser available, Pants will run a local web server in order to receive an OAuth token and automatically save it to disk. It will also open a browser window so you can log into Toolchain with your GitHub credentials. 

On machines without a web browser, in-terminal prompts will guide you through manually completing the authentication process.

On completion, you'll be asked to name your token. This description will be visible within the Toolchain web application's [_Pants client tokens_](https://app.toolchain.com/tokens/) page:

![](https://files.readme.io/1748b66-2022-07-05_at_12.52_PM.png "2022-07-05 at 12.52 PM.png")

The authentication token will be saved to your filesystem at `./.pants.d/toolchain_auth/auth_token.json` -- the `pants.d` directory is usually included under `.gitignore` in Pants repositories. If the authentication token is saved elsewhere, ensure that it is not committed to your repository.

Each user authentication will last for 180 days, during which time the user will not need to run `auth-acquire` again. During the 10 days before the token expires, the user will be prompted to run `auth-acquire` again to ensure they experience no interruptions in service.

> 📘 Advanced options
> 
> To force the manual authentication workflow, use `./pants --auth-acquire-headless`.

> 🚧 Authentication tokens are per-repo
> 
> Toolchain authentication tokens are scoped to specific repositories. If a given user wants to use the Toolchain plugin for multiple repositories on the same machine, they will need to follow the authentication steps on each repository.

#### Verify that Buildsense is working for local builds

Once you have a token for local development, all future Pants runs on that machine should be logged by Buildsense. To verify this, run a sample Pants command, such as linting a single source file:

```
./pants lint path/to/source/file
```

If Pants can successfully connect to Toolchain, your console output should resemble a usual Pants run, with no additional warnings due to communication failutres.

You should be able to navigate to your repository in Buildsense, and see each Pants run in your build history:

![](https://files.readme.io/853776c-2022-07-05_at_1.32_PM.png "2022-07-05 at 1.32 PM.png")

This screenshot shows a successful linting run.

### Add CI authentication (organization owner only)

In a previous step, we configured Pants to read authentication details in CI from an environment variable called `TOOLCHAIN_AUTH_TOKEN`.

To generate an auth token value for use in CI, your organization owner must run the following command:

```
./pants auth-acquire --auth-acquire-for-ci
```

As well as outputting the token to the console, rather than storing the token in a file, the `--auth-acquire-for-ci` option instructs Toolchain to generate a token that is usable in CI environments. You can run this command on any machine with Pants installed, but the steps on GitHub must be taken as an organization owner for relevant repositories.

As with authenticating locally, this process will run a local web server to receive an OAuth token, and will pop open a web browser so you can log into Toolchain. If successful, you will be asked to name your token, and the token itself will be echoed to your console:

```
Enter token description [ip-192-168-1-112.ec2.internal [for CI]]:
Access Token is: *REDACTED*
```

Copy the token from your terminal window (represented by `*REDACTED*` in the above output, the actual token will be quite a long string).

Store the value of the token as an encrypted secret with your CI provider, and expose it to the steps of your CI workflow that run Pants as an environment variable called `TOOLCHAIN_AUTH_TOKEN`. Consult your CI provider's documentation for specific steps on how to do this (see, for example: [GitHub Actions docs](https://docs.github.com/en/actions/security-guides/encrypted-secrets), [CircleCI docs](https://support.circleci.com/hc/en-us/articles/360006717953-Storing-Secret-Files-certs-etc-)).

> 🚧 You must store your token immediately
> 
> Toolchain does not store authentication tokens on our system. The only time a token will be visible is at the time you generate it.
> 
> Ensure that you copy and store the authentication token immediately, as it will not be available anywhere else.

#### Verify that CI configuration is functioning correctly

The Toolchain plugin will attempt to detect which CI provider is being used, and use environment variables provided by that provider to determine which GitHub user's is responsible for the commit that has triggered a given build. 

If configured correctly, CI Builds will be reported in your Buildsense logs as belonging to that user, and not the user who initially created the token.

Secondly, Toolchain's remote cache features should now be enabled. You can verify this by triggering CI with two commits in sequence, with each commit modifying different files.

The CI job triggered by the second commit should fetch results from actions run by the first commit's CI job, from the cache.

To verify that the remote cache is working correctly, locate the most recent CI build on your Buildsense dashboard, click "Details", then "metrics". You should see non-zero values for:

- - Remote cache requests\*,
- - Remote cache requests cached\*.

> 📘 Supported CI providers
> 
> The Toolchain pants plugin can automatically detect CI environments from the following providers:
> 
> - CircleCI
> - GitHub Actions

### Next steps

#### Streamline your CI cache setup

Once you have verified that Toolchain's remote cache is working, you should adjust your CI's cache configuration to save it from doing duplicate work. In particular, some Pants local cache directories store the results of processes that will also be sent to the remote cache. These directories can get quite large, and will impact build performance.

We recommend only caching `~/.cache/pants/setup`, and using a cache key based on the runner's OS platform and the contents of your `pants.toml` file.

In GitHub actions, suitable `key` and `path` settings would be:

```
          key: ${{ runner.os }}-${{ hashFiles('pants*toml') }}-v2
          path: |
             ~/.cache/pants/setup
```
# Changelog #

## 0.28.0 -- UNPUBLISHED ##

* TBD

## 0.27.0 -- 2023-04-12 ##

* Resolve error installing rules on Pants 2.17.0.dev4 and above arising from a `hasattr` check that no longer works.

## 0.26.0 -- 2023-01-20 ##

* Remove support for Pants 2.13 and older. Only Pants 2.14 and above are supported.
* Update for deprecation of `Environment` in favor of `EnvironmentVars`.

## 0.25.0 -- 2022-11-02 ##

* Marks the plugin's `Goal`s as having migrated to the new target Environments support, using only local environment settings.
* Improve reliability of batch upload (used to retry upload of build data from previous runs where the upload failed).

## 0.24.0 -- 2022-10-11 ##

* Remove support for Pants 2.11 and older. Only Pants 2.12 and above are supported.
* Add the option to show auth token JWT claims data as json: `[auth-token-info].json`, so for example: `./pants auth-token-info --auth-token-info-json` will output the claims data as a json string (single line).
* Stop using pants deprecated SubsystemRule API.
* Add `auth-token-check` goal that will check if the Toolchain auth token is about to expire and fill fail (exit code -1) if it is about to expire (with a specified threshold via `[auth-token-check].threshold`) or if it had already expired.
* Add initial support for remote execution permissions and configuration (via auth plugin).
* Improve logging (context) when logging token load.

## 0.23.0 -- 2022-09-26 ##

* Add a `auth-token-info` goal to show access token info (token ID & expiration time).
* Add `JWT` to list used to filter out environment variables uploaded to buildsense for CI integration (list already had: `ACCESS,` `TOKEN` and `SECRET`).

## 0.22.0 -- 2022-08-17 ##

* Tweak authentication success message.
* Always use multipart file upload to upload buildsense data.
* Increase timeout for buildsene data upload from 5 to 10 seconds.

## 0.21.0 -- 2022-07-27 ##

* **BREAKING CHANGE**  Add `--auth-acquire-for-ci` option to acquire tokens to be used in CI (org owners/admins only). This now implies `--auth-acquire-output=console`.
* Removed support for Pants's old option system. Only the new option system is supported, which means the plugin supports Pants 2.11 and above.
* Remove support for Travis-CI.
* Add support for configuring the remote cache address using Toolchain Servers (`[GLOBAL].remote_store_address` can be removed from pants.toml in pants v2.14 and above).
* Improve error messages when auth fails.
* Handle transient errors when they occur (retries).
* Add support for [remote auth plugin name](https://github.com/pantsbuild/pants/pull/16171) attribute (pants 2.14 and above).
* Add entry point support the auth plugin so the `[GLOBAL].remote_auth_plugin` option can be removed from pants configuration (pants 2.14 and above).

## 0.20.0 -- 2022-06-06 ##

* Add support for [new pants VCS/GIT APIs](https://github.com/pantsbuild/pants/pull/15030)
* Bugfix: Don't use FileOption for `[auth].auth_file` options since it requires the file to exist (breaks onboarding)
* Improve error handling when server rejects auth token request. Allow showing error messages from the server.
* Add support for showing server messages/notifications on the console.

## 0.19.0 -- 2022-05-09 ##

* Add extra space before token to make it easier to select for copy & paste.
* Add support for handling multiple parents for workunits.
* Fix `log_final_upload_latency` option type from string to boolean when using Pants' legacy options API.
* Migrate from per-workunit to global metrics capture.

## 0.18.0 -- 2022-04-08 ##

* Add the ability to collect platform information (opt-in, this is off by default).
  The following information is collected: OS type, OS Version, Python Version, Python Implementation, Platform architecture, CPU type, number of CPU cores and RAM size.
  This is similar to the data collected by pants [anonymous telemetry subsystem](https://www.pantsbuild.org/docs/anonymous-telemetry): `[buildsense].collect_platform_data`.
* Consume CI Capture config from the config object in the response.
* Add support for the new Pants Options API for Pants 2.11 and up. Old versions of the API, used in pants 2.10 and earlier are still supported.
* Add an option to log latency for BuildSense final upload: `[buildsense].log_final_upload_latency`.

## 0.17.0 -- 2022-01-03 ##

* Specifying an org name (slug) under `[toolchain-setup]` is now required.
* Support for configuring CI integration (capturing CI Environment variables) from buildsense.
  This allows toolchain to add support for additional CI systems without shipping new versions of the plugin.
* Loosen the requirement for `requests` to a range.

## 0.16.0 -- 2021-12-14 ##

* Buildsense work unit converter configuration (what artifacts and metadata get uploaded to the buildsense service) is now controlled from the buildsense service instead of being hard coded into the plugin.
* Add the ability to specify org (customer/account) name in the `[toolchain-setup]` section. This is optional in this version and will be mandatory in the next version.

## 0.15.0 -- 2021-10-19 ##

* Capture per-workunit target addresses to provide more detailed build information.
* Bugfix: Don't queue up workunits in memory when buildsense is disabled.

## 0.14.0 -- 2021-09-13 ##

* Add support for capturing environment variables for [Bitbucket Pipelines](https://support.atlassian.com/bitbucket-cloud/docs/variables-and-secrets/) and [Buildkite](https://buildkite.com/docs/pipelines/environment-variables)
* Fix an issue where runs that completed quickly would be recorded as `NOT_FINISHED`.
* Add support for capturing new metadata for processes to assist with cache hit rate optimization.
* Improve logging when acquiring restricted access tokens.
* Allow configuration of token renew threshold (default 30m).
* Show link to pants run BuildSense in the console.

## 0.13.1 -- 2021-07-13 ##

* Fix issue w/ logs not propagating properly from buildsense reporter thread.
* Fix issue when git work tree can not be determined.
* Add an explicit dependency on chardet since the requests library is removing that dependency.

## 0.13.0 -- 2021-06-16 ##

* Add support for setting a description field when acquiring a token
* Logging improvement for auth code
* Re-enable async completion for streaming work unit handler logic (buildsense data upload)

## 0.12.0 -- 2021-06-01 ##

* Fix issue with decoding tokens (handle missing padding)
* Simplify config (single location for base url)
* Exclude environment variables that might contain secrets or sensitive data
* Buildsense now enabled by default.

## 0.11.0 -- 2021-05-12 ##

* Added support for new remote cache auth plugin APIs introduced in <https://github.com/pantsbuild/pants/pull/12029>

## 0.10.0 -- 2021-05-10 ##

* toolchain_auth_plugin (used for remote_auth_plugin) now accepts **kwargs so arguments can be added without breaking the interface.
* Fix headers handling in the remoting auth plugin to also support remote execution headers and to not override all headers set outside the plugin.
* Remove dependency on python-dateutil
* Avoid trying to load token from an environment variable unless auth.from_env_var is explicitly set

## 0.9.1 -- 2021-04-29 ##

* Fix issue with restricted token environment matcher

## 0.9.0 -- 2021-04-29 ##

* Remove dependency on setuptools
* Always upload log to buildsense
* New auth pages
* Refactor local web-server
* Add logic to test auth pages w/o running auth flow
* Add support for requiring an environment variable match before requesting a restricted token (to avoid requesting a restricted tokens when running in forks)

## 0.8.1 -- 2021-04-08 ##

* Fixed bad dependencies path in setup.py entry point.

## 0.8.0 -- 2021-04-08 ##

* Usage of auto-registration mechanism via setup.py entry_points so no need to specify backends anymore.
* Removed support for python 3.9 since pants doesn't support it yet.
* Disabled async completion due to issues w/ pants logging and not uploading data to buildsense in some cases.
* Log when attempting to load auth token from env variables (used in CI)

## 0.6.0 -- 2021-03-01 ##

* Support pants API for counters & targets spec.
* Fix GitHub Actions CI integration.

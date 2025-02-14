# Toolchain Plugin for Pants

This plugin provides Toolchain specific functionality for pants.

* Authenticating with the toolchain service and storing auth token in local file system (or displaying it in the console for CI config scenarios)
* Uploading runs/builds data into buildsense.
* Acquiring tokens to use w/ the pants remoting client (for remote cache)

## Testing & Publishing a new version of the plugin

1. Test new version of the plugin in with the pants repo.
    * Build a dist: `./pants package src/python/toolchain:toolchain-pants-plugin`
    * Add the `toolchain/dist` to the pants repo pants.toml, for example:

        ```toml
        [python-repos]
        find_links = "file:///Users/asher/projects/toolchain/dist/"
        ```

    * Update the version of the toolchain plugin under the plugins section in pants.toml:

        ```toml
            plugins = ["toolchain.pants.plugin==NEW-VERSION-NUMBER"]
        ```

    * Run some pants commands (lint, typecheck, test) on the pants repo and make sure the plugin works:
        i.e. the runs show up in the buildsense UI and remote caching is being properly used (check the build details metrics tab).

2. Run the script to upload a new version:
    * Update the release date of the version you're about to release in the [CHANGELOG.md](CHANGELOG.md).
    * Run `./prod/python/toolchain_dev/upload_plugin_to_pypi.sh --real-pypi`
        * Note that running the script without the `--real-pypi` flag, will upload the plugin to test.pypi.org and won't update the [changelog](https://docs.toolchain.com/docs/toolchain-pants-plugin-changelog) in the [toolchain docs site](https://docs.toolchain.com/)
3. Submit a PR to:
    * Include your release date bump from the previous step.
    * Bump the version number of the plugin in [version.py](version.py).
    * Add a section for the new version to [CHANGELOG.md](CHANGELOG.md).
4. Submit a PR to the pants repo upgrading the new plugin (i.e. changing the plugin requirement in pants.toml) [Example](https://github.com/pantsbuild/pants/pull/11543)

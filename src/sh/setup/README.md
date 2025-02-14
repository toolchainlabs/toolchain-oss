# Setting up local tools

## Ensure Env

Every time you run `./python` we call `ensure_env.sh` to ensure that python3 virtualenvs are up to date
with the current requirements.txt.

## Homebrew [OSX Only]

On OSX, the `ensure_env.sh` script also runs `homebrew.sh` which ensures we have a specific version of homebrew,
distinct from your system's standard homebrew, and canonical locations for python3, postgresql and any
other packages required by the toolchain repo. You can access these packages directly with e.g.,
`~/.toolchain/homebrew/bin/python`.

This script exits early if `~/.toolchain/homebrew/homebrew_packages.txt` matches
`3rdparty/homebrew/homebrew_packages.txt`

Homebrew is installed in the user's homedir so that multiple checkouts of the toolchain repo can use the same
homebrew. In the event of a breaking update of a homebrew installed binary or homebrew itself, this can be
versioned by changing the value of `TOOLCHAIN_HOMEBREW` in `src/sh/setup/ensure_env.sh`

To install additional packages with this homebrew, use `~/.toolchain/homebrew/bin/brew install <your package here>`.
Update the `${TOOLCHAIN_HOMEBREW} install ...` line in `src/sh/setup/install_homebrew.sh` while you're at it.
This will not update homebrew packages for everyone, but anyone getting started will at least have the
right packages installed automatically.

## Python Virtualenv

These ensure all current requirements in `3rdparty/python::` have been pip installed into your virtualenv.
The virtualenvs are recreated whenever the hash of the recursive contents of `3rdparty/python` change.

## Ipython

To use the ipython repl, `export TOOLCHAIN_PYTHON3=.venv3/bin/ipython3` in your .bashrc.

To have the setup script install ipython in your virtualenvs by default, `export TOOLCHAIN_INSTALL_IPYTHON="yes"`
in your bashrc and delete .venv3/requirements.txt to force setup to run again. If you prefer to do this
manually use `./python -m pip install ipython`

A handy way to automate this is to install [direnv](https://direnv.net/) and add a .envrc file to the root of the repo.

eg:

```sh
export PATH="/Users/tansypants/.toolchain/homebrew/bin:$PATH"
export TOOLCHAIN_PYTHON3=".venv3/bin/ipython3"
export TOOLCHAIN_USE_IPYTHON="yes"
```

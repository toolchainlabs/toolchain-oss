#!/bin/bash -eux
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Add the vagrant user to the `docker` group so Docker is permitted without sudo.
sudo usermod -a -G docker vagrant

# Setup pyenv.
export PYENV_ROOT="${HOME}/.pyenv"
export PATH="${PYENV_ROOT}/bin:${PATH}"
mkdir "${PYENV_ROOT}"
cp -r /usr/local/opt/pyenv/. "${PYENV_ROOT}"
eval "$(pyenv init -)"
pyenv install 3.9.12 && pyenv global 3.9.12

# Add per-login setup to `.bashrc`.
cat >>"${HOME}/.bashrc" <<'EOF'

# *** TOOLCHAIN EDITS ***

# Enable pyenv.
export PYENV_ROOT="${HOME}/.pyenv"
export PATH="${PYENV_ROOT}/bin:${PATH}"
eval "$(pyenv init -)"

# Enable direnv.
eval "$(direnv hook bash)"

# kubectl completion
if command -v kubectl >/dev/null 2>&1 ; then
  source <(kubectl completion bash)
fi

# helm completion
if command -v helm >/dev/null 2>&1 ; then
  source <(helm completion bash)
fi

# AWS completer
if command -v aws_completer >/dev/null 2>&1 ; then
  complete -C "$(command -v aws_completer)" aws
fi

export PATH="${HOME}/bin:${PATH}"
EOF

# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    overrides={
        "curl.py": {"resolve": "pants-plugin"},
    },
)

python_tests(name="tests")

pex_binary(name="ensure_ecr_repo", entry_point="ensure_ecr_repo.py")
pex_binary(name="ensure_k8s_service_role", entry_point="ensure_k8s_service_role.py")
pex_binary(name="ensure_secrets", entry_point="ensure_secrets.py")
pex_binary(name="get_referrals", entry_point="get_referrals.py")
pex_binary(name="rotate_jwt_secrets", entry_point="rotate_jwt_secrets.py")
pex_binary(name="bump_ver_tool", entry_point="bump_ver_tool.py")
pex_binary(name="sync_grafana_dashboards", entry_point="sync_grafana_dashboards.py")
pex_binary(name="publish_pants_plugin", entry_point="publish_pants_plugin.py")

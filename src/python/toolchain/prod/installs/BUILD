# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()

python_test_utils(name="test_utils")

python_tests(
    name="tests",
    timeout=90,
    dependencies=[
        "src/python/toolchain/servicerouter:images",
        "prod/helm:helm-charts",
    ],
)


pex_binary(name="build_install_services_dev", entry_point="build_install_services_dev.py")
pex_binary(name="build_install_services_prod", entry_point="build_install_services_prod.py")
pex_binary(name="deploy_toolchain_spa_dev", entry_point="deploy_toolchain_spa_dev.py")
pex_binary(name="deploy_toolchain_spa_prod", entry_point="deploy_toolchain_spa_prod.py")
pex_binary(name="deploy_pants_demosite_dev", entry_point="deploy_pants_demosite_dev.py")
pex_binary(name="deploy_pants_demosite_prod", entry_point="deploy_pants_demosite_prod.py")
pex_binary(name="install_influxdb", entry_point="install_influxdb.py")
pex_binary(name="install_cert_mgr_prod", entry_point="install_cert_mgr_prod.py")
pex_binary(name="build_install_remote_cache_reporter", entry_point="build_install_remote_cache_reporter.py")
pex_binary(name="install_monitoring_prod", entry_point="install_monitoring_prod.py")
pex_binary(name="install_service_prod", entry_point="install_service_prod.py")
pex_binary(name="install_grafana_prod", entry_point="install_grafana_prod.py")
pex_binary(name="install_logging_prod", entry_point="install_logging_prod.py")
pex_binary(name="install_logging_dev", entry_point="install_logging_dev.py")
pex_binary(name="install_aws_alb_ingress_controller", entry_point="install_aws_alb_ingress_controller.py")
pex_binary(name="install_external_dns_prod", entry_point="install_external_dns_prod.py")
pex_binary(name="install_posthog_dev", entry_point="install_posthog_dev.py")
pex_binary(name="install_aws_efs_driver", entry_point="install_aws_efs_driver.py")
pex_binary(name="purge_old_buildsenese_lambda_versions", entry_point="purge_old_buildsenese_lambda_versions.py")

# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

from toolchain.buildsense.ingestion.run_processors.options_extrator import get_pants_options
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture


def test_get_pants_options() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    options_data = get_pants_options(build_data)
    assert options_data is not None
    options_file, artifact_dict = options_data
    assert artifact_dict == {
        "name": "pants_options",
        "description": "Pants Options",
        "artifacts": "pants_options.json",
        "content_types": ["pants_options"],
    }
    assert options_file.name == "pants_options.json"
    assert options_file.content_type == "application/json"
    assert json.loads(options_file.content) == [
        {
            "content_type": "pants_options",
            "name": "Options",
            "content": {
                "GLOBAL": {
                    "build_file_prelude_globs": [],
                    "ca_certs_path": None,
                    "colors": True,
                    "concurrent": False,
                    "dynamic_ui": True,
                    "exclude_target_regexp": [],
                    "files_not_found_behavior": "warn",
                    "ignore_pants_warnings": ["DEPRECATED: option 'stats_version' in scope 'run-tracker'"],
                    "level": "info",
                    "local_execution_root_dir": "/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T",
                    "local_store_dir": "/Users/asher/.cache/pants/lmdb_store",
                    "log_levels_by_target": {},
                    "log_show_rust_3rdparty": False,
                    "logdir": None,
                    "loop": False,
                    "loop_max": 4294967296,
                    "plugins_force_resolve": False,
                    "print_stacktrace": True,
                    "process_execution_cleanup_local_dirs": True,
                    "process_execution_local_enable_nailgun": False,
                    "process_execution_local_parallelism": 12,
                    "process_execution_remote_parallelism": 128,
                    "process_execution_speculation_delay": 1,
                    "verify_config": True,
                }
            },
        }
    ]


def test_get_pants_options_no_options() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    del build_data["recorded_options"]
    assert get_pants_options(build_data) is None

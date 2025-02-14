# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.buildsense.ingestion.run_processors.zipkin_trace import create_zipkin_trace
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture


def test_create_zipkin_trace_files_singular_parent() -> None:
    workunits_json = load_fixture("build_end_workunits_v3")["workunits"]
    trace = create_zipkin_trace("pants_run_2020_05_07_09_54_18_542_e2204cccbe534499befbc04c8da2f886", workunits_json)
    assert trace == load_fixture("zipkin_trace_1")
    assert len(trace) == 200
    assert sum(1 for wu in trace if "parentId" in wu) == 199


def test_create_zipkin_trace_files_missing_duration_singular_parent() -> None:
    workunits_json = load_fixture("build_end_v3_missing_end_ts")["workunits"]
    trace = create_zipkin_trace("pants_run_2020_05_15_20_55_51_468_6caca4513f92485fb088c9dac3ba8bc7", workunits_json)
    assert trace == load_fixture("zipkin_trace_2")


def test_create_zipkin_trace_files() -> None:
    workunits_json = load_fixture("pants_jvm_rules_run")["workunits"]
    trace = create_zipkin_trace("pants_run_2022_05_09_16_32_29_279_b049f1b088ca4d88a61492d5429a1338", workunits_json)
    assert trace == load_fixture("zipkin_trace_3")
    assert len(trace) == 60
    # NB: This run has four workunit roots, and so four workunits without parents.
    assert sum(1 for wu in trace if "parentId" in wu) == 56

# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# This pylint ignore is due to the migration of the pants options API, when we remove backward compatibility we should also remove this line
# pylint: disable=unexpected-keyword-arg
from __future__ import annotations

import base64
import logging
import multiprocessing
import os
import platform
import socket
import time
from dataclasses import asdict
from pathlib import Path
from threading import Thread
from typing import Mapping

from pants.engine.internals import native_engine  # type: ignore[attr-defined]
from pants.engine.streaming_workunit_handler import StreamingWorkunitContext, TargetInfo, WorkunitsCallback
from pants.option.option_value_container import OptionValueContainer

from toolchain.pants.auth.store import AuthStore
from toolchain.pants.buildsense.client import BuildSenseClient
from toolchain.pants.buildsense.common import RunTrackerBuildInfo, WorkUnits, WorkUnitsMap
from toolchain.pants.buildsense.state import BuildState
from toolchain.pants.buildsense.subsystems import CaptureCIEnv, Reporter

logger = logging.getLogger(__name__)


class ReporterCallback(WorkunitsCallback):
    """Configuration for Toolchain's BuildSense reporting."""

    def __init__(
        self,
        options: OptionValueContainer | Reporter,
        auth_store: AuthStore,
        env: Mapping[str, str],
        repo_name: str | None,
        org_name: str | None,
        base_url: str,
        git_worktree,
    ):
        super().__init__()
        self._env = env
        self._enabled = False
        if not options.enable:
            logger.debug("BuildSense plugin is disabled.")
            return
        if not repo_name:
            logger.warning("Couldn't determine repo name. BuildSense plugin will be disabled.")
            return
        client = BuildSenseClient.from_options(
            client_options=options, auth=auth_store, repo=repo_name, org_name=org_name, base_url=base_url
        )
        # set self._build_state *before* changing the state.
        self._build_state = BuildState(
            client,
            local_store_base_path=Path(options.local_store_base),
            max_batch_size_mb=options.max_batch_size_mb,
            local_store_enabled=options.local_build_store,
            log_final_upload_latency=options.log_final_upload_latency,
        )

        self._enabled = True
        self._git_worktree = git_worktree
        self._log_upload = options.log_upload
        self._call_count = 0
        self._reporter_thread = ReportThread(self._build_state)
        self._options = options
        self.__ci_capture: CaptureCIEnv | None = None
        self._build_link_logged = not options.show_link
        logger.debug("BuildSense Plugin enabled")

    @property
    def can_finish_async(self) -> bool:
        return True

    def __call__(  # type: ignore[override]
        self,
        *,
        completed_workunits: WorkUnits,
        started_workunits: WorkUnits,
        context: StreamingWorkunitContext,
        finished: bool = False,
        **kwargs,
    ) -> None:
        if not self._enabled:
            return
        self.handle_workunits(
            completed_workunits=completed_workunits,
            started_workunits=started_workunits,
            context=context,
            finished=finished,
        )

    def handle_workunits(
        self,
        *,
        completed_workunits: WorkUnits,
        started_workunits: WorkUnits,
        context: StreamingWorkunitContext,
        finished: bool,
    ) -> None:
        work_units_map = {wu["span_id"]: wu for wu in (started_workunits or [])}
        work_units_map.update({wu["span_id"]: wu for wu in (completed_workunits or [])})
        logger.debug(
            f"handle_workunits total={len(work_units_map)} completed={len(completed_workunits)} started={len(started_workunits)} finished={finished} calls={self._call_count}"
        )
        self._maybe_show_buildsense_link()
        self._build_state.set_context(context)
        if self._call_count == 0 and not finished:
            # If the first invocation of ReporterCallback by pants is also the last one
            # (i.e. if finished=True), then we don't send the initial report to buildsense.

            self._enqueue_initial_report(context)
        if finished:
            self._on_finish(context, self._call_count, work_units_map)
        else:
            self._build_state.queue_workunits(self._call_count, work_units_map)
        self._call_count += 1

    def _maybe_show_buildsense_link(self) -> None:
        if not self._build_link_logged and self._build_state.build_link:
            logger.info(f"View on BuildSense: {self._build_state.build_link}")
            self._build_link_logged = True

    @property
    def _ci_capture(self) -> CaptureCIEnv:
        if not self.__ci_capture:
            self.__ci_capture = CaptureCIEnv(
                pattern=self._options.ci_env_var_pattern,
                exclude_terms=list(self._options.ci_env_scrub_terms),
                ci_map=self._build_state.ci_capture_config,
            )
        return self.__ci_capture

    def _enqueue_initial_report(self, context: StreamingWorkunitContext) -> None:
        run_tracker_info = self._get_run_tracker_info(context)
        logger.debug(f"enqueue_initial_report {run_tracker_info.run_id}")
        self._build_state.queue_initial_report(run_tracker_info)

    def _on_finish(self, context: StreamingWorkunitContext, call_count: int, work_units_map: WorkUnitsMap) -> None:
        run_tracker_info = self._get_run_tracker_info(context)
        self._build_state.build_ended(run_tracker_info, call_count=call_count, work_units_map=work_units_map)
        self._reporter_thread.stop_thread()

    def _get_run_tracker_info(self, context: StreamingWorkunitContext) -> RunTrackerBuildInfo:
        ci_env = self._ci_capture.capture(self._env)
        run_tracker = context.run_tracker
        has_ended = run_tracker.has_ended()
        # Copy the RunTracker info before mutating it in _adjust_run_info_fields.
        run_info = dict(run_tracker.run_information())
        _adjust_run_info_fields(run_info, run_tracker.goals, has_ended, scm=self._git_worktree)

        build_stats = {
            "run_info": run_info,
            "recorded_options": run_tracker.get_options_to_record(),
        }

        if ci_env:
            build_stats["ci_env"] = ci_env

        if has_ended:
            if self._options.collect_platform_data:
                build_stats["platform"] = collect_platform_info()

            build_stats.update(
                {
                    "pantsd_stats": run_tracker.pantsd_scheduler_metrics,
                    "cumulative_timings": run_tracker.get_cumulative_timings(),  # type: ignore[dict-item]
                    "counter_names": list(run_tracker.counter_names),  # type: ignore[dict-item]
                }
            )
            targets_specs = _get_expanded_specs(context)
            if targets_specs:
                build_stats["targets"] = targets_specs
            counters = _get_counters(context)
            if counters:
                build_stats["counters"] = counters
            observation_histograms = _get_histograms(context)
            if observation_histograms:
                build_stats["observation_histograms"] = observation_histograms
        upload_log = all((has_ended, self._log_upload, run_tracker.run_logs_file))
        log_file = Path(run_tracker.run_logs_file) if upload_log else None
        return RunTrackerBuildInfo(has_ended=has_ended, build_stats=build_stats, log_file=log_file)


def _get_expanded_specs(context: StreamingWorkunitContext) -> dict[str, list[dict[str, str]]] | None:
    def to_targets_dicts(targets: list[TargetInfo]) -> list[dict[str, str]]:
        return [asdict(target) for target in targets]

    targets = context.get_expanded_specs().targets
    return {spec: to_targets_dicts(targets) for spec, targets in targets.items()}


def _get_counters(context: StreamingWorkunitContext) -> dict[str, int] | None:
    # TODO: The `get_metrics` method was added in Pants 2.11.x. Can remove when we no longer want
    # to support older versions.
    if not hasattr(context, "get_metrics"):
        return None
    return context.get_metrics()


def _get_histograms(context: StreamingWorkunitContext) -> dict | None:
    histograms_info = context.get_observation_histograms()
    version = histograms_info["version"]

    if version != 0:
        logger.warning(f"Cannot encode internal metrics histograms: unexpected version {version}")
        return None
    histograms = histograms_info["histograms"]
    if not histograms:
        return None
    return {
        "version": version,
        "histograms": {key: base64.b64encode(value).decode() for key, value in histograms.items()},
    }


def _adjust_run_info_fields(run_info: dict, goals: list[str], has_ended: bool, scm) -> None:
    host = socket.gethostname()
    run_info["machine"] = f"{host} [docker]" if _is_docker() else host
    if scm:
        revision = scm.commit_id
        run_info.update(revision=revision, branch=scm.branch_name or revision)
    else:
        logger.warning("Can't get git scm info")

    if "parent_build_id" in run_info:
        del run_info["parent_build_id"]

    run_info["computed_goals"] = goals
    if not has_ended:
        run_info["outcome"] = "NOT_AVAILABLE"


def _is_docker() -> bool:
    # Based on https://github.com/jaraco/jaraco.docker/blob/master/jaraco/docker.py
    # https://stackoverflow.com/a/49944991/38265
    cgroup = Path("/proc/self/cgroup")
    return Path("/.dockerenv").exists() or (cgroup.exists() and "docker" in cgroup.read_text("utf-8"))


class ReportThread:
    def __init__(self, build_state: BuildState) -> None:
        self._logging_destination = native_engine.stdio_thread_get_destination()
        self._build_state = build_state
        self._terminate = False
        self._reporter_thread = Thread(target=self._report_loop, name="buildsense-reporter", daemon=True)
        self._reporter_thread.start()

    def stop_thread(self):
        self._terminate = True
        self._reporter_thread.join()

    def _report_loop(self):
        native_engine.stdio_thread_set_destination(self._logging_destination)
        while not self._terminate:
            operation = self._build_state.send_report()
            if operation.is_sent():
                # If we send something in this call, then we don't need to sleep.
                continue
            time.sleep(2 if operation.is_error() else 0.05)
        self._build_state.send_final_report()


def collect_platform_info() -> dict[str, str | int]:
    platform_info = platform.uname()
    try:  # https://stackoverflow.com/a/28161352/38265
        mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError) as err:
        logger.warning(f"failed to read memory size: {err!r}")
        mem_bytes = -1
    return {
        "os": platform_info.system,
        "os_release": platform_info.release,
        "processor": platform_info.processor,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "architecture": platform.machine(),
        "cpu_count": multiprocessing.cpu_count(),
        "mem_bytes": mem_bytes,
    }

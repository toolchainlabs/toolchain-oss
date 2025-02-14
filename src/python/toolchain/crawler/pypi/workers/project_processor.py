# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.pypi.json_api import NoProjectData, get_project_data
from toolchain.crawler.pypi.models import ProcessDistribution, ProcessProject
from toolchain.lang.python.distributions.distribution_type import DistributionType, UnsupportedDistributionType
from toolchain.packagerepo.pypi.models import Distribution, Project, Release
from toolchain.workflow.error import AdvisoryWorkException
from toolchain.workflow.worker import Worker


class ProjectProcessor(Worker):
    work_unit_payload_cls = ProcessProject

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._project_data = None

    def do_work(self, work_unit_payload):
        if work_unit_payload.num_distributions is not None:
            return True

        try:
            self._project_data = get_project_data(work_unit_payload.project_name, work_unit_payload.required_serial)
        except NoProjectData as ex:
            raise AdvisoryWorkException(str(ex))
        # Convert the packagetype to our DistributionType. Must be done in on_work, so we can
        # raise an advisory exception if it fails.
        for dist_dicts in self._project_data.values():
            for dist_dict in dist_dicts:
                try:
                    dist_dict["dist_type"] = DistributionType.from_setuptools_packagetype(
                        dist_dict["packagetype"]
                    ).value
                except UnsupportedDistributionType as ex:
                    raise AdvisoryWorkException(str(ex))

        return False

    def on_reschedule(self, work_unit_payload):
        project = Project.get_or_create(work_unit_payload.project_name)
        dists = []
        for version, dist_dicts in self._project_data.items():
            if " " in version:
                # We've encountered at least one messed-up project that used a human-readable paragraph as a version
                # (https://pypi.org/pypi/sysv_ipc/json), presumably due to error in their setup.py.
                # We heuristically detect insane errors like that here.
                continue
            release = Release.get_or_create(project, version)
            for dist_dict in dist_dicts:
                dist = Distribution.get_or_create_from_dict(dist_dict, release, work_unit_payload.required_serial)
                work_unit_payload.distributions.add(dist)
                dists.append(dist)
        work_unit_payload.num_distributions = len(dists)

        # Don't try to process .exe, .rpm etc.
        processable_dists = [dist for dist in dists if dist.dist_type in ProcessDistribution.processable_dist_types]

        # Acquire a lock on Project, to avoid race conditions around creating duplicate work.
        Project.objects.filter(id=project.id).select_for_update()

        dist_ids_with_existing_process_work = set(
            ProcessDistribution.objects.filter(distribution__release__project=project).values_list("distribution_id")
        )
        remaining_process_work = ProcessDistribution.objects.bulk_create(
            [
                ProcessDistribution(distribution=dist)
                for dist in processable_dists
                if dist.id not in dist_ids_with_existing_process_work
            ]
        )
        remaining_fetch_work = FetchURL.objects.bulk_create(
            [FetchURL(url=process_work.distribution.url) for process_work in remaining_process_work]
        )
        for process_work, fetch_work in zip(remaining_process_work, remaining_fetch_work):
            process_work.add_requirement_by_id(fetch_work.work_unit_id)
            work_unit_payload.add_requirement_by_id(process_work.work_unit_id)

# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.base.crawler_work_dispatcher import CrawlerWorkDispatcher
from toolchain.crawler.pypi.workers.all_projects_processor import AllProjectsProcessor
from toolchain.crawler.pypi.workers.all_projects_shard_processor import AllProjectsShardProcessor
from toolchain.crawler.pypi.workers.changelog_processor import ChangelogProcessor
from toolchain.crawler.pypi.workers.distribution_data_dumper import DistributionDataDumper
from toolchain.crawler.pypi.workers.distribution_processor import DistributionProcessor
from toolchain.crawler.pypi.workers.leveldb_updater import LevelDbUpdater
from toolchain.crawler.pypi.workers.periodic_changelog_processor import PeriodicChangelogProcessor
from toolchain.crawler.pypi.workers.periodic_leveldb_updater import PeriodicLevelDbUpdater
from toolchain.crawler.pypi.workers.project_processor import ProjectProcessor
from toolchain.crawler.pypi.workers.pypi_url_fetcher import PypiURLFetcher
from toolchain.workflow.work_dispatcher import WorkerClasses


class PypiCrawler(CrawlerWorkDispatcher):
    """A workflow dispatcher that performs crawl work."""

    @classmethod
    def get_all_worker_classes(cls) -> WorkerClasses:
        return (
            AllProjectsProcessor,
            AllProjectsShardProcessor,
            ChangelogProcessor,
            DistributionProcessor,
            DistributionDataDumper,
            LevelDbUpdater,
            PeriodicChangelogProcessor,
            PeriodicLevelDbUpdater,
            ProjectProcessor,
            PypiURLFetcher,
        )

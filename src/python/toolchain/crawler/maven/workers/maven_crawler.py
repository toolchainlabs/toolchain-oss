# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.base.crawler_work_dispatcher import CrawlerWorkDispatcher
from toolchain.crawler.maven.workers.latest_maven_artifact_indexer import LatestMavenArtifactIndexer
from toolchain.crawler.maven.workers.link_page_processor import LinkPageProcessor
from toolchain.crawler.maven.workers.maven_artifact_indexer import MavenArtifactIndexer
from toolchain.crawler.maven.workers.maven_metadata_processor import MavenMetadataProcessor
from toolchain.crawler.maven.workers.maven_url_fetcher import MavenURLFetcher
from toolchain.crawler.maven.workers.parent_pom_locator import ParentPOMLocator
from toolchain.crawler.maven.workers.pom_information_extractor import POMInfoExtractor
from toolchain.workflow.work_dispatcher import WorkerClasses


class MavenCrawler(CrawlerWorkDispatcher):
    @classmethod
    def get_all_worker_classes(cls) -> WorkerClasses:
        return (
            MavenURLFetcher,
            LinkPageProcessor,
            MavenMetadataProcessor,
            ParentPOMLocator,
            POMInfoExtractor,
            MavenArtifactIndexer,
            LatestMavenArtifactIndexer,
        )

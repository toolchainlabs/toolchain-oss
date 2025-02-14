# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import subprocess

from django.conf import settings

from toolchain.aws.s3 import S3
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.base.crawler_worker_base import CrawlerWorkerBase
from toolchain.crawler.maven.models import BINARY, SOURCE, IndexMavenArtifact, MavenArtifactKytheEntries
from toolchain.crawler.maven.workers import index_sources
from toolchain.packagerepo.maven.artifact_locator import ArtifactLocator


class MavenArtifactIndexer(CrawlerWorkerBase):
    """Invokes kythe indexer on a maven artifact version."""

    DEFAULT_LEASE_SECS = 1800

    work_unit_payload_cls = IndexMavenArtifact

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._entries_s3_key = None
        self._entries_compression = MavenArtifactKytheEntries.GZTAR

    def _coords_segments(self, coords):
        return coords.group_id.split(".") + [coords.artifact_id, coords.version]

    def _upload_to_s3(self, local_path, coords, s3_file_name):
        s3_path_segments = ["index", "jvm"] + self._coords_segments(coords) + [s3_file_name]
        path = "/".join(s3_path_segments)
        self._entries_s3_key = f"/{settings.KYTHE_ENTRIES_KEY_PREFIX}/entries/{path}"
        S3().upload_file(
            settings.KYTHE_ENTRIES_BUCKET, self._entries_s3_key, local_path, content_type="binary/octet-stream"
        )

    @staticmethod
    def _run_command(args):
        with subprocess.Popen(args=args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            stdoutdata, stderrdata = proc.communicate()
            if proc.returncode:
                raise ToolchainAssertion(
                    f"Indexer failed with exit code {proc.returncode}.\nSTDOUT: {stdoutdata}.\n\nSTDERR: {stderrdata}\n"
                )
            return stdoutdata

    def index_source_jar(self, work_unit_payload):
        """Run the kythe indexer over a source jar and return the path to the archived output."""
        return index_sources.index_source_jar(
            work_unit_payload.coordinates(), "./indexer-buildgen", self._entries_compression.lower()
        )

    def index_binary_jar(self, work_unit_payload):
        """Run the kythe indexer over a binary jar and return the path to the archived output."""
        coords = work_unit_payload.coordinates()
        jar_url = ArtifactLocator.binary_jar_url(coords)
        archive_path = os.path.join("./dist", "bin.index.entries")
        args = [
            "./pants",
            "index-artifact.kythe-binary-jar",
            f"--index-artifact-kythe-binary-jar-jar-url={jar_url}",
            f"--index-artifact-kythe-binary-jar-archive-path={archive_path}",
            f"--index-artifact-kythe-binary-jar-archive={self._entries_compression.lower()}",
        ]
        self._run_command(args)
        compression_suffix = MavenArtifactKytheEntries.get_compression_suffix(self._entries_compression)
        return f"{archive_path}{compression_suffix}"

    def do_work(self, work_unit_payload):
        index_func = {SOURCE: self.index_source_jar, BINARY: self.index_binary_jar}
        kind = work_unit_payload.kind
        local_path = index_func[kind](work_unit_payload)
        compression_suffix = MavenArtifactKytheEntries.get_compression_suffix(self._entries_compression)
        s3_file_name = f"{kind.lower()}.index.entries{compression_suffix}"

        self._upload_to_s3(local_path=local_path, coords=work_unit_payload.coordinates(), s3_file_name=s3_file_name)
        os.remove(local_path)
        return True

    def on_success(self, work_unit_payload):
        MavenArtifactKytheEntries.objects.get_or_create(
            artifact=work_unit_payload.artifact,
            version=work_unit_payload.version,
            kind=work_unit_payload.kind,
            defaults={
                "location": S3.get_s3_url(settings.KYTHE_ENTRIES_BUCKET, self._entries_s3_key),
                "compression": self._entries_compression,
            },
        )

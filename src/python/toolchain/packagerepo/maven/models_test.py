# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.packagerepo.maven.models import MavenArtifact, MavenArtifactVersion


@pytest.mark.django_db(transaction=True)
class TestModels:
    def test_artifact_version_ordering(self):
        ma = MavenArtifact.objects.create(group_id="foo", artifact_id="bar")
        mav1_1 = MavenArtifactVersion.objects.create(artifact=ma, version="1.1")
        mav1_10 = MavenArtifactVersion.objects.create(artifact=ma, version="1.10")
        mav1_2 = MavenArtifactVersion.objects.create(artifact=ma, version="1.2")
        mav1_3_beta = MavenArtifactVersion.objects.create(artifact=ma, version="1.3-beta")

        all_versions_sorted = ma.all_versions()
        assert [mav1_10, mav1_3_beta, mav1_2, mav1_1] == all_versions_sorted

        latest = ma.latest_version()
        assert mav1_10 == latest

        mav1_20_1 = MavenArtifactVersion.objects.create(artifact=ma, version="1.20.1")

        all_versions_sorted = ma.all_versions()
        assert [mav1_20_1, mav1_10, mav1_3_beta, mav1_2, mav1_1] == all_versions_sorted

        latest = ma.latest_version()
        assert mav1_20_1 == latest

        mav1_3_1 = MavenArtifactVersion.objects.create(artifact=ma, version="1.3.1")

        all_versions_sorted = ma.all_versions()
        assert [mav1_20_1, mav1_10, mav1_3_1, mav1_3_beta, mav1_2, mav1_1] == all_versions_sorted

        latest = ma.latest_version()
        assert mav1_20_1 == latest

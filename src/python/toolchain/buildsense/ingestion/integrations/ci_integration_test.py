# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.buildsense.ingestion.integrations.ci_integration import (
    BitBucketPipelines,
    Buildkite,
    CircleCI,
    GithubActionsCI,
    InvalidCIData,
    TravisCI,
    get_ci_info,
)
from toolchain.buildsense.records.run_info import RunType, ScmProvider
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture


class TestCircleCI:
    def test_empty(self) -> None:
        assert CircleCI.get_ci_info({}) is None

    def test_not_circle_ci(self) -> None:
        ci_env = load_fixture("travis_pull_request_env")
        assert CircleCI.get_ci_info(ci_env) is None

    def test_pull_request(self) -> None:
        ci_env = load_fixture("circleci_pull_request_env")
        ci_full_details = CircleCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.ref_name == "pull/6470"
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.sha1 == "27f8b0c3d8878d94ab79725bd09b9e886fea3b0c"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.PULL_REQUEST
        assert ci_details.pull_request == 6470
        assert ci_details.ref_name == "pull/6470"
        assert ci_details.username == "asherf"
        assert ci_details.job_name == "build"
        assert ci_details.build_num == 22462
        assert ci_details.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/22462"

    def test_branch(self) -> None:
        ci_env = load_fixture("circleci_branch_env")
        ci_full_details = CircleCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.ref_name == "susan"
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.sha1 == "e01dbc17ce149e005052e82625115936dbe26729"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.ref_name == "susan"
        assert ci_details.pull_request is None
        assert ci_details.username == "asherf"
        assert ci_details.job_name == "build"
        assert ci_details.build_num == 22465
        assert ci_details.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/22465"

    @pytest.mark.parametrize(
        "url",
        [
            "http://jerry.com",
            "http://circleci.com/gh/toolchainlabs/toolchain/22465",
            "http://circleci.com.jerry.evil.com/",
            "https://travis-ci.com/toolchainlabs/example-python/builds/179800609",
        ],
    )
    def test_dont_allow_any_url(self, url) -> None:
        ci_env = load_fixture("circleci_branch_env")
        ci_env["CIRCLE_BUILD_URL"] = ""
        ci_full_details = CircleCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.ref_name == "susan"
        assert ci_full_details.sha1 == "e01dbc17ce149e005052e82625115936dbe26729"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.ref_name == "susan"
        assert ci_details.pull_request is None
        assert ci_details.username == "asherf"
        assert ci_details.job_name == "build"
        assert ci_details.build_num == 22465
        assert ci_details.build_url is None


class TestTravisCI:
    def test_empty(self) -> None:
        assert TravisCI.get_ci_info({}) is None

    def test_not_travis_ci(self) -> None:
        ci_env = load_fixture("circleci_branch_env")
        assert TravisCI.get_ci_info(ci_env) is None

    def test_pull_request(self) -> None:
        ci_env = load_fixture("travis_pull_request_env")
        ci_full_details = TravisCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.ref_name == "repr"
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.sha1 == "b286d52ad3af2e469f8b3f664168dbc9cbbe3b0d"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.PULL_REQUEST
        assert ci_details.pull_request == 10576
        assert ci_details.username == "asherf"
        assert ci_details.ref_name == "repr"
        assert ci_details.job_name == "Build Linux native engine and pants.pex (Python 3.6)"
        assert ci_details.build_num == 34753
        assert ci_details.build_url == "https://travis-ci.com/pantsbuild/pants/builds/179009029"

    def test_branch(self) -> None:
        ci_env = load_fixture("travis_branch_env")
        ci_full_details = TravisCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.ref_name == "cosmo"
        assert ci_full_details.sha1 == "1cdd4f3eff1beade14bfdbb3019349051674efd1"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.pull_request is None
        assert ci_details.username == ""
        assert ci_details.ref_name == "cosmo"
        assert ci_details.job_name == ""
        assert ci_details.build_num == 18
        assert ci_details.build_url == "https://travis-ci.com/toolchainlabs/example-python/builds/179800609"

    def test_branch_partial(self) -> None:
        ci_env = load_fixture("travis_branch_start_1")["ci_env"]
        ci_full_details = TravisCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.ref_name == "festivus"
        assert ci_full_details.sha1 is None
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.pull_request is None
        assert ci_details.username == ""
        assert ci_details.job_name is None
        assert ci_details.build_num == 92
        assert ci_details.ref_name == "festivus"
        assert ci_details.build_url is None

    @pytest.mark.parametrize(
        "url",
        [
            "https://jerry.com",
            "http://travis-ci.com/toolchainlabs/example-python/builds/179800609",
            "https://travis-ci.org/toolchainlabs/example-python/builds/179800609",
            "https://travis-ci.com.jerry.evil.com/",
            "http://travis-ci.com.jerry.evil.com/",
            "https://circleci.com/gh/toolchainlabs/toolchain/22465",
        ],
    )
    def test_dont_allow_any_url(self, url) -> None:
        ci_env = load_fixture("travis_branch_env")
        ci_env["TRAVIS_BUILD_WEB_URL"] = url
        ci_full_details = TravisCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.ref_name == "cosmo"
        assert ci_full_details.sha1 == "1cdd4f3eff1beade14bfdbb3019349051674efd1"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.ref_name == "cosmo"
        assert ci_details.pull_request is None
        assert ci_details.username == ""
        assert ci_details.job_name == ""
        assert ci_details.build_num == 18
        assert ci_details.build_url is None


class TestGithubActionsCI:
    def test_empty(self) -> None:
        assert GithubActionsCI.get_ci_info({}) is None

    def test_not_github_actions_ci(self) -> None:
        ci_env = load_fixture("circleci_branch_env")
        assert GithubActionsCI.get_ci_info(ci_env) is None

    def test_pull_request(self) -> None:
        ci_env = load_fixture("github_actions_pr_env")
        ci_full_details = GithubActionsCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.ref_name == "seinfeld"
        assert ci_full_details.sha1 == "4a55a7d2b3b2b5d37dd36bf1f8d8628426e604d3"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.PULL_REQUEST
        assert ci_details.pull_request == 7011
        assert ci_details.ref_name == "seinfeld"
        assert ci_details.username == "asherf"
        assert ci_details.job_name == "Remote Execution Tests [integration-tests]"
        assert ci_details.build_num == 539
        assert ci_details.build_url == "https://github.com/toolchainlabs/toolchain/actions/runs/564395592"

    def test_branch(self) -> None:
        ci_env = load_fixture("github_actions_branch_env")
        ci_full_details = GithubActionsCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.ref_name == "master"
        assert ci_full_details.sha1 == "3d357d9f4769390d726220b234ec5ffcece97f7e"
        assert ci_full_details.has_branch_name is True
        ci_details = ci_full_details.details
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.pull_request is None
        assert ci_details.ref_name == "master"
        assert ci_details.username == "asherf"
        assert ci_details.job_name == "Pants/Buildsense Github Integrations [bootstrap_pants]"
        assert ci_details.build_num == 21
        assert ci_details.build_url == "https://github.com/toolchainlabs/toolchain/actions/runs/572486586"

    def test_tag(self) -> None:
        ci_env = load_fixture("github_actions_tag_env")
        ci_full_details = GithubActionsCI.get_ci_info(ci_env)
        assert ci_full_details is not None
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.ref_name == "test-branch"
        assert ci_full_details.has_branch_name is False
        assert ci_full_details.sha1 == "da75f05cadb42d8e1a06655f021fab86c5857f4d"
        ci_details = ci_full_details.details
        assert ci_details.run_type == RunType.TAG
        assert ci_details.pull_request is None
        assert ci_details.username == "asherf"
        assert ci_details.ref_name == "test-branch"
        assert ci_details.job_name == "Pants/Buildsense Github Integrations [bootstrap_pants]"
        assert ci_details.build_num == 1897
        assert ci_details.build_url == "https://github.com/toolchainlabs/toolchain/actions/runs/764828518"

    def test_pr_with_invalid_ref(self) -> None:
        # we have seen this in prod, not sure how this happens but we need to handle it.
        ci_env = load_fixture("github_actions_pr_invalid_ref_env")
        with pytest.raises(InvalidCIData, match="Github Actions PR: can't parse github_ref"):
            GithubActionsCI.get_ci_info(ci_env)

    def test_pr_with_invalid_ref_get_ci_info(self) -> None:
        # we have seen this in prod, not sure how this happens but we need to handle it.
        ci_env = load_fixture("github_actions_pr_invalid_ref_env")
        assert get_ci_info(ci_env, context="puddy") is None


class TestBitBucketPipelines:
    def test_empty(self) -> None:
        assert BitBucketPipelines.get_ci_info({}) is None

    def test_not_bitbucket_ci(self) -> None:
        ci_env = load_fixture("circleci_branch_env")
        assert BitBucketPipelines.get_ci_info(ci_env) is None

    def test_pull_request(self) -> None:
        ci_env = load_fixture("bitbucket_pr_env")
        ci_full_details = BitBucketPipelines.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.scm == ScmProvider.BITBUCKET
        assert ci_full_details.ref_name == "jerry"
        assert ci_full_details.sha1 == "8ec2113681b3"
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.PULL_REQUEST
        assert ci_details.pull_request == 8
        assert ci_details.username == ""
        assert ci_details.job_name == "Bitbucket pipeline job"
        assert ci_details.ref_name == "jerry"
        assert ci_details.build_num == 22
        assert (
            ci_details.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/22/steps/%7B8ba1cdd9-6e43-444e-8630-19e4e073c675%7D"
        )

    def test_branch(self) -> None:
        ci_env = load_fixture("bitbucket_branch_env")
        ci_full_details = BitBucketPipelines.get_ci_info(ci_env)
        assert ci_full_details is not None
        assert ci_full_details.scm == ScmProvider.BITBUCKET
        assert ci_full_details.ref_name == "upgrades"
        assert ci_full_details.sha1 == "5ff4f0e9c70c04d3cc8ccd26d644efa237f12b0e"
        assert ci_full_details.has_branch_name is True
        ci_details = ci_full_details.details
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.pull_request is None
        assert ci_details.username == ""
        assert ci_details.job_name == "Bitbucket pipeline job"
        assert ci_details.ref_name == "upgrades"
        assert ci_details.build_num == 18
        assert (
            ci_details.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/18/steps/%7Ba2be828b-d8dc-4d69-b3f1-89ef5712b1dc%7D"
        )

    def test_tag(self) -> None:
        ci_env = load_fixture("bitbucket_tag_env")
        ci_full_details = BitBucketPipelines.get_ci_info(ci_env)
        assert ci_full_details is not None
        assert ci_full_details.scm == ScmProvider.BITBUCKET
        assert ci_full_details.ref_name == "h&h-bagles"
        assert ci_full_details.sha1 == "113feb0671944c44d274fc4d7c32c681427f9011"
        assert ci_full_details.has_branch_name is False
        ci_details = ci_full_details.details
        assert ci_details.run_type == RunType.TAG
        assert ci_details.pull_request is None
        assert ci_details.ref_name == "h&h-bagles"
        assert ci_details.username == ""
        assert ci_details.job_name == "Bitbucket pipeline job"
        assert ci_details.build_num == 33
        assert (
            ci_details.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/33/steps/%7Bf987bb55-e706-49f5-9a2d-6ade1f16ee5f%7D"
        )


class TestBuildkite:
    def test_empty(self) -> None:
        assert Buildkite.get_ci_info({}) is None

    def test_not_bitbucket_ci(self) -> None:
        ci_env = load_fixture("circleci_branch_env")
        assert Buildkite.get_ci_info(ci_env) is None

    def test_bitbucket_pull_request(self) -> None:
        ci_env = load_fixture("buildkite_bitbucket_pull_request_lint_run")["ci_env"]
        ci_full_details = Buildkite.get_ci_info(ci_env)
        assert ci_full_details is not None
        ci_details = ci_full_details.details
        assert ci_full_details.ref_name == "costanza"
        assert ci_full_details.sha1 == "9cc2cb733f514128754ff5c9f00664fad66af642"
        assert ci_full_details.scm == ScmProvider.BITBUCKET
        assert ci_full_details.has_branch_name is True
        assert ci_details.run_type == RunType.PULL_REQUEST
        assert ci_details.ref_name == "costanza"
        assert ci_details.pull_request == 24
        assert ci_details.username == ""
        assert ci_details.job_name == "Pants Lint"
        assert ci_details.build_num == 49
        assert (
            ci_details.build_url
            == "https://buildkite.com/toolchain-labs/pants-minimal/builds/49#3292fdf1-e913-41a9-868f-a51cae7a61d6"
        )

    def test_bitbucket_branch(self) -> None:
        ci_env = load_fixture("buildkite_bitbucket_branch_lint_run")["ci_env"]
        ci_full_details = Buildkite.get_ci_info(ci_env)
        assert ci_full_details is not None
        assert ci_full_details.ref_name == "main"
        assert ci_full_details.scm == ScmProvider.BITBUCKET
        assert ci_full_details.sha1 == "284731de0f774148578dcd2304ed9df25a95abe3"
        assert ci_full_details.has_branch_name is True
        ci_details = ci_full_details.details
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.pull_request is None
        assert ci_details.ref_name == "main"
        assert ci_details.username == ""
        assert ci_details.job_name == "Pants Lint"
        assert ci_details.build_num == 54
        assert (
            ci_details.build_url
            == "https://buildkite.com/toolchain-labs/pants-minimal/builds/54#972c04e0-e2df-42be-91ed-e236c6e9531b"
        )

    def test_github_branch(self) -> None:
        ci_env = load_fixture("buildkite_github_branch_lint_run")["ci_env"]
        ci_full_details = Buildkite.get_ci_info(ci_env)
        assert ci_full_details is not None
        assert ci_full_details.ref_name == "main"
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.sha1 == "8c72128f7f930dd6658c4b2723f48dc431860e6c"
        assert ci_full_details.has_branch_name is True
        ci_details = ci_full_details.details
        assert ci_details.run_type == RunType.BRANCH
        assert ci_details.pull_request is None
        assert ci_details.username == ""
        assert ci_details.job_name == "Pants Lint"
        assert ci_details.ref_name == "main"
        assert ci_details.build_num == 3
        assert (
            ci_details.build_url
            == "https://buildkite.com/toolchain-labs/minimal-pants-github/builds/3#e5e98dcf-23f0-48d4-87f0-c1ffbf023c2a"
        )

    def test_github_pull_request(self) -> None:
        ci_env = load_fixture("buildkite_github_pull_request_lint_run")["ci_env"]
        ci_full_details = Buildkite.get_ci_info(ci_env)
        assert ci_full_details is not None
        assert ci_full_details.ref_name == "jerry"
        assert ci_full_details.scm == ScmProvider.GITHUB
        assert ci_full_details.sha1 == "b3635292e22d7bf19998e9cacf3d31ed4d86c77d"
        assert ci_full_details.has_branch_name is True
        ci_details = ci_full_details.details
        assert ci_details.run_type == RunType.PULL_REQUEST
        assert ci_details.pull_request == 3
        assert ci_details.username == ""
        assert ci_details.ref_name == "jerry"
        assert ci_details.job_name == "Pants Lint"
        assert ci_details.build_num == 9
        assert (
            ci_details.build_url
            == "https://buildkite.com/toolchain-labs/minimal-pants-github/builds/9#d4bbd917-7dca-4f22-a84f-41a049ae4921"
        )

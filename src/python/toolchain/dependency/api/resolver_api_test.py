# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from pathlib import Path

import pytest

from toolchain.dependency.api.views_test import BaseViewsTest
from toolchain.dependency.constants import ErrorType
from toolchain.dependency.models import ResolveDependencies, ResolverSolution
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.test_helpers.pypi_test_data import DistributionsSet
from toolchain.satresolver.test_helpers.pypi_utils import create_fake_depgraph
from toolchain.util.leveldb.test_helpers.utils import FakeReloadableDataset


class TestResolveViewSet(BaseViewsTest):
    @pytest.fixture()
    def fake_depgraph_dataset(self, tmp_path: Path) -> Depgraph:
        db_path = tmp_path / "leveldbs" / "77362"
        db_path.mkdir(parents=True)
        return create_fake_depgraph(db_path, *DistributionsSet.dist_set_1)

    def test_get_resolve_for_maven(self, client) -> None:
        response = client.post("/v1/packagerepo/maven/resolve/")
        assert response.status_code == 400
        assert response.json() == {"detail": "API not supported for 'maven'"}

    def test_get_resolve_for_pypi_requirements_missing_dependencies(self, client) -> None:
        response = client.post("/v1/packagerepo/pypi/resolve/")
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "dependencies": [{"code": "required", "message": "This field is required."}],
                "platform": [{"code": "required", "message": "This field is required."}],
                "py": [{"code": "required", "message": "This field is required."}],
            }
        }

    def test_get_resolve_for_pypi_requirements_missing_python_requirement(self, client) -> None:
        response = client.post("/v1/packagerepo/pypi/resolve/", data={"dependencies": []}, format="json")
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "dependencies": [{"code": "required", "message": "This field is required."}],
                "platform": [{"code": "required", "message": "This field is required."}],
                "py": [{"code": "required", "message": "This field is required."}],
            }
        }

    def test_bad_reqs(self, client, settings, fake_depgraph_dataset: Depgraph) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        reqs = ["aaa<2.0.0", "mr_mandelbaum; oh_no='smug'"]
        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            format="json",
            data={"dependencies": reqs, "py": "3.3", "abi": "abi3", "platform": "any"},
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"dependencies": [{"code": "", "message": "Parse error at \"'; oh_no='\": Expected string_end"}]}
        }

    def test_empty_reqs(self, client, settings, fake_depgraph_dataset: Depgraph) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            format="json",
            data={"dependencies": [], "py": "3.3", "abi": "abi3", "platform": "any"},
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {"dependencies": [{"code": "required", "message": "This field is required."}]}
        }

    def test_queue_resolve(self, client, settings, fake_depgraph_dataset: Depgraph) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        assert ResolverSolution.objects.count() == 0
        assert ResolveDependencies.objects.count() == 0
        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            data={"dependencies": ["aaa==1.0.0"], "py": "3.3", "abi": ["cp37m", "abi3"], "platform": "any"},
            format="json",
        )
        assert response.status_code == 200
        assert ResolverSolution.objects.count() == 1
        assert ResolveDependencies.objects.count() == 1
        solution = ResolverSolution.objects.first()
        resolve = ResolveDependencies.objects.first()
        assert response.json() == {"solution": {"id": solution.id, "state": "pending"}}
        assert resolve.solution_id == solution.id
        assert resolve.python_requirements == ["aaa==1.0.0"]
        assert resolve.parameters == {"abis": ["abi3", "cp37m"], "python": "3.3", "platform": "any"}

    def test_resolve_already_queued(self, client, settings, fake_depgraph_dataset: Depgraph) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        solution_id = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0", "aaa==1.0.0"],
            parameters={"python": "3.8", "abis": ["cp37m", "abi3"], "platform": "linux"},
            leveldb_version=77362,
        ).solution_id

        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            data={
                "dependencies": ["aaa==1.0.0", "tinsel==1.22.0"],
                "py": "3.8",
                "abi": ["cp37m", "abi3"],
                "platform": "linux",
            },
            format="json",
        )
        assert response.status_code == 200
        assert ResolverSolution.objects.count() == 1
        solution = ResolverSolution.objects.first()
        assert solution.id == solution_id
        assert response.json() == {"solution": {"id": solution.id, "state": "pending"}}

    def test_resolve_already_solved(self, client, settings, fake_depgraph_dataset: Depgraph) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        solution_id = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0", "aaa==1.0.0"],
            parameters={"python": "3.8", "abis": ["cp37m", "abi3"], "platform": "linux"},
            leveldb_version=77362,
        ).solution_id
        ResolverSolution.store_solution(
            solution_id, {"releases": [{"project_name": "tinsel", "version": "1.222.33", "sha256": "low-talker"}]}
        )
        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            data={
                "dependencies": ["aaa==1.0.0", "tinsel==1.22.0"],
                "py": "3.8",
                "abi": ["cp37m", "abi3"],
                "platform": "linux",
            },
            format="json",
        )
        assert response.status_code == 200
        assert ResolverSolution.objects.count() == 1
        assert response.json() == {
            "releases": [{"project_name": "tinsel", "version": "1.222.33", "sha256": "low-talker"}],
            "data_version": 77362,
        }

    def test_get_result_not_existing(self, client) -> None:
        response = client.get("/v1/packagerepo/pypi/resolve/ovaltine/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_solution_pending(self, client) -> None:
        solution_id = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.7", "abi": ["cp37m", "abi3"], "platform": "any"},
            leveldb_version=1212,
        ).solution_id
        response = client.get(f"/v1/packagerepo/pypi/resolve/{solution_id}/")
        assert response.status_code == 200
        assert response.json() == {
            "solution": {"id": solution_id, "state": "pending"},
        }

    def test_get_solution_error(self, client) -> None:
        solution_id = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.7", "abi": ["cp37m", "abi3"], "platform": "any"},
            leveldb_version=1212,
        ).solution_id
        ResolverSolution.store_solution(
            solution_id,
            {
                "available_versions": ["1.3.2", "1.3.13", "1.3.4", "1.3.14"],
                "msg": "No matching distributions found for moto==1.3.15.dev883",
                "package_name": "moto",
            },
            error_type=ErrorType.PACKAGE_NOT_FOUND,
        )
        response = client.get(f"/v1/packagerepo/pypi/resolve/{solution_id}/")
        assert response.status_code == 406
        assert response.json() == {
            "error": {
                "available_versions": ["1.3.2", "1.3.13", "1.3.4", "1.3.14"],
                "msg": "No matching distributions found for moto==1.3.15.dev883",
                "package_name": "moto",
            },
            "data_version": 1212,
        }

    def test_get_solution(self, client) -> None:
        solution_id = ResolverSolution.get_or_create(
            dependencies=["tinsel==1.22.0"],
            parameters={"py": "3.7", "abi": ["cp37m", "abi3"], "platform": "any"},
            leveldb_version=8319,
        ).solution_id
        ResolverSolution.store_solution(
            solution_id, {"releases": [{"project_name": "tinsel", "version": "1.222.33", "sha256": "low-talker"}]}
        )
        response = client.get(f"/v1/packagerepo/pypi/resolve/{solution_id}/")
        assert response.status_code == 200
        assert response.json() == {
            "releases": [{"project_name": "tinsel", "version": "1.222.33", "sha256": "low-talker"}],
            "data_version": 8319,
        }

    def test_max_reqs(self, client, settings, fake_depgraph_dataset: Depgraph) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        deps = [f"mandelbaum-{i}==2.{i}.33" for i in range(201)]
        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            format="json",
            data={"dependencies": deps, "py": "3.8", "abi": "abi3", "platform": "win32"},
        )
        assert response.status_code == 400
        assert response.json() == {
            "errors": {
                "dependencies": [
                    {
                        "code": "invalid",
                        "message": "Exceeded maximum number of dependencies per request (max: 200, got: 201)",
                    }
                ]
            }
        }

    @pytest.mark.parametrize(
        "dependencies",
        [
            [
                'pylint==1.9.4;python_version<"3.7"',
                'mock==4.0.1; python_version>="3.0"',
                'mock==3.0.5;python_version == "2.7"',
            ]
        ],
    )
    def test_queue_resolve_reqs_with_constrains(
        self, dependencies, client, settings, fake_depgraph_dataset: Depgraph
    ) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        assert ResolverSolution.objects.count() == 0
        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            data={"dependencies": dependencies, "py": "3.7", "abi": ["abi3"], "platform": "manylinux2014_x86_64"},
            format="json",
        )
        assert response.status_code == 200
        assert ResolverSolution.objects.count() == 1
        assert ResolveDependencies.objects.count() == 1
        solution = ResolverSolution.objects.first()
        resolve = ResolveDependencies.objects.first()
        assert response.json() == {"solution": {"id": solution.id, "state": "pending"}}
        assert resolve.solution_id == solution.id
        assert resolve.python_requirements == [
            'pylint==1.9.4; python_version < "3.7"',
            'mock==4.0.1; python_version >= "3.0"',
            'mock==3.0.5; python_version == "2.7"',
        ]
        assert resolve.parameters == {"abis": ["abi3"], "platform": "manylinux2014_x86_64", "python": "3.7"}

    def test_queue_resolve_no_abi(self, client, settings, fake_depgraph_dataset: Depgraph) -> None:
        settings.DEPGRAPH = FakeReloadableDataset(fake_depgraph_dataset)
        assert ResolverSolution.objects.count() == 0
        assert ResolverSolution.objects.count() == 0
        response = client.post(
            "/v1/packagerepo/pypi/resolve/",
            data={
                "dependencies": ["requests==2.2.0", "boto3==1.13.12"],
                "py": "3.7",
                "platform": "macosx_10_15_x86_64",
            },
            format="json",
        )
        assert response.status_code == 200
        assert ResolverSolution.objects.count() == 1
        solution = ResolverSolution.objects.first()
        resolve = ResolveDependencies.objects.first()
        assert response.json() == {"solution": {"id": solution.id, "state": "pending"}}
        assert resolve.solution_id == solution.id
        assert resolve.python_requirements == ["requests==2.2.0", "boto3==1.13.12"]
        assert resolve.parameters == {"abis": ["abi3", "cp37m"], "python": "3.7", "platform": "macosx_10_15_x86_64"}

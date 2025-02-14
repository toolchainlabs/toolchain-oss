# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest

from toolchain.lang.python.distributions.distribution_reader import get_modules_for_dist
from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.lang.python.test_helpers.utils import extract_distribution, load_fixture

_existence_modules = {"existence"}

_django_modules = set(load_fixture("django_modules.txt").split())

_requests_modules = {
    "requests",
    "requests.adapters",
    "requests.api",
    "requests.auth",
    "requests.certs",
    "requests.compat",
    "requests.cookies",
    "requests.exceptions",
    "requests.help",
    "requests.hooks",
    "requests.models",
    "requests.packages",
    "requests.sessions",
    "requests.status_codes",
    "requests.structures",
    "requests.utils",
}


_froglabs_modules = {"froglabs", "froglabs.cli", "froglabs.clients", "froglabs.exceptions", "froglabs.utils"}


_twitter_common_collection_modules = {
    "twitter",
    "twitter.common",
    "twitter.common.collections",
    "twitter.common.collections.ordereddict",
    "twitter.common.collections.orderedset",
    "twitter.common.collections.ringbuffer",
}


_zstandard_modules = {"zstd", "_zstd_cffi"}


_pex_203_modules = {
    "pex",
    "pex.bin",
    "pex.bin.pex",
    "pex.bootstrap",
    "pex.commands",
    "pex.commands.bdist_pex",
    "pex.common",
    "pex.compatibility",
    "pex.compiler",
    "pex.distribution_target",
    "pex.environment",
    "pex.executor",
    "pex.finders",
    "pex.glibc",
    "pex.interpreter",
    "pex.interpreter_constraints",
    "pex.jobs",
    "pex.orderedset",
    "pex.package",
    "pex.pep425tags",
    "pex.pex",
    "pex.pex_bootstrapper",
    "pex.pex_builder",
    "pex.pex_info",
    "pex.pex_warnings",
    "pex.pip",
    "pex.platforms",
    "pex.requirements",
    "pex.resolver",
    "pex.testing",
    "pex.third_party",
    "pex.tracer",
    "pex.util",
    "pex.variables",
    "pex.vendor",
    "pex.version",
}


_pex_217_modules = _pex_203_modules - {"pex.pep425tags", "pex.package", "pex.glibc"} | {"pex.dist_metadata"}


_raptorq_modules = {"raptorq"}


_termcolor_modules = {"termcolor"}


_netuitive_modules = {
    "netuitive",
    "netuitive.attribute",
    "netuitive.client",
    "netuitive.element",
    "netuitive.event",
    "netuitive.metric",
    "netuitive.relation",
    "netuitive.sample",
    "netuitive.tag",
}


_databricks_connect_modules = {
    "pyspark",
    "pyspark.accumulators",
    "pyspark.broadcast",
    "pyspark.cloudpickle",
    "pyspark.conf",
    "pyspark.context",
    "pyspark.daemon",
    "pyspark.databricks",
    "pyspark.databricks.iter_utils",
    "pyspark.databricks.koalas",
    "pyspark.databricks.koalas.usage_logger",
    "pyspark.databricks_connect",
    "pyspark.dbutils",
    "pyspark.files",
    "pyspark.find_spark_home",
    "pyspark.heapq3",
    "pyspark.java_gateway",
    "pyspark.join",
    "pyspark.ml",
    "pyspark.ml.base",
    "pyspark.ml.classification",
    "pyspark.ml.clustering",
    "pyspark.ml.common",
    "pyspark.ml.evaluation",
    "pyspark.ml.feature",
    "pyspark.ml.fpm",
    "pyspark.ml.image",
    "pyspark.ml.linalg",
    "pyspark.ml.param",
    "pyspark.ml.param.shared",
    "pyspark.ml.pipeline",
    "pyspark.ml.recommendation",
    "pyspark.ml.regression",
    "pyspark.ml.stat",
    "pyspark.ml.tests",
    "pyspark.ml.tuning",
    "pyspark.ml.util",
    "pyspark.ml.wrapper",
    "pyspark.mllib",
    "pyspark.mllib.classification",
    "pyspark.mllib.clustering",
    "pyspark.mllib.common",
    "pyspark.mllib.evaluation",
    "pyspark.mllib.feature",
    "pyspark.mllib.fpm",
    "pyspark.mllib.linalg",
    "pyspark.mllib.linalg.distributed",
    "pyspark.mllib.random",
    "pyspark.mllib.recommendation",
    "pyspark.mllib.regression",
    "pyspark.mllib.stat",
    "pyspark.mllib.stat.KernelDensity",
    "pyspark.mllib.stat.distribution",
    "pyspark.mllib.stat.test",
    "pyspark.mllib.tests",
    "pyspark.mllib.tree",
    "pyspark.mllib.util",
    "pyspark.profiler",
    "pyspark.python.pyspark.shell",
    "pyspark.rdd",
    "pyspark.rddsampler",
    "pyspark.resultiterable",
    "pyspark.serializers",
    "pyspark.shell",
    "pyspark.shuffle",
    "pyspark.sql",
    "pyspark.sql.catalog",
    "pyspark.sql.column",
    "pyspark.sql.conf",
    "pyspark.sql.context",
    "pyspark.sql.dataframe",
    "pyspark.sql.functions",
    "pyspark.sql.group",
    "pyspark.sql.readwriter",
    "pyspark.sql.session",
    "pyspark.sql.streaming",
    "pyspark.sql.tests",
    "pyspark.sql.types",
    "pyspark.sql.udf",
    "pyspark.sql.utils",
    "pyspark.sql.window",
    "pyspark.statcounter",
    "pyspark.status",
    "pyspark.storagelevel",
    "pyspark.streaming",
    "pyspark.streaming.context",
    "pyspark.streaming.dstream",
    "pyspark.streaming.flume",
    "pyspark.streaming.kafka",
    "pyspark.streaming.kinesis",
    "pyspark.streaming.listener",
    "pyspark.streaming.tests",
    "pyspark.streaming.util",
    "pyspark.taskcontext",
    "pyspark.test_broadcast",
    "pyspark.test_serializers",
    "pyspark.tests",
    "pyspark.traceback_utils",
    "pyspark.util",
    "pyspark.version",
    "pyspark.worker",
    "pyspark.wrapped_python",
}


_micropython_hashlib5_modules = {"hashlib", "hashlib.test_sched"}


_pymasker_modules = {"pymasker"}

_pyobject_modules = {
    "pyobject.search",
    "pyobject.browser",
    "pyobject",
    "pyobject.test.pyc_zipper",
    "pyobject.newtypes",
    "pyobject.test",
    "pyobject.test.testcode",
    "pyobject.code_",
}


@pytest.mark.parametrize(
    ("distribution_name", "distribution_type", "modules"),
    [
        ("existence-0.1.3.zip", DistributionType.SDIST, _existence_modules),
        ("Django-1.6.11.tar.gz", DistributionType.SDIST, _django_modules),
        ("requests-2.22.0.tar.gz", DistributionType.SDIST, _requests_modules),
        ("requests-2.22.0-py2.py3-none-any.whl", DistributionType.WHEEL, _requests_modules),
        ("froglabs-0.1.3-py3.6.egg", DistributionType.SDIST, _froglabs_modules),
        ("twitter.common.collections-0.3.11.tar.gz", DistributionType.SDIST, _twitter_common_collection_modules),
        ("zstandard-0.8.0-cp26-cp26m-win_amd64.whl", DistributionType.WHEEL, _zstandard_modules),
        ("pex-2.0.3-py2.py3-none-any.whl", DistributionType.WHEEL, _pex_203_modules),
        ("pex-2.0.3.tar.gz", DistributionType.SDIST, _pex_203_modules),
        ("pex-2.1.7-py2.py3-none-any.whl", DistributionType.WHEEL, _pex_217_modules),
        ("pex-2.1.7.tar.gz", DistributionType.SDIST, _pex_217_modules),
        # A rust-cpython sdist, and a wheel built from it.
        ("raptorq-1.3.1.tar.gz", DistributionType.SDIST, _raptorq_modules),
        ("raptorq-1.3.1-cp37-cp37m-manylinux1_x86_64.whl", DistributionType.WHEEL, _raptorq_modules),
        # SDists with unconventional layouts.
        ("termcolor-1.1.0.tar.gz", DistributionType.SDIST, _termcolor_modules),
        ("netuitive-0.1.4.tar.gz", DistributionType.SDIST, _netuitive_modules),
        ("databricks-connect-6.3.1.tar.gz", DistributionType.SDIST, _databricks_connect_modules),
        ("micropython-hashlib5-2.4.2.post7.tar.gz", DistributionType.SDIST, _micropython_hashlib5_modules),
        ("pymasker-0.2.3.tar.gz", DistributionType.SDIST, _pymasker_modules),
        ("pycopy-test.support-0.2.2.tar.gz", DistributionType.SDIST, set()),
        ("pyobject---1.2.0.tar.gz", DistributionType.SDIST, _pyobject_modules),
    ],
)
def test_get_modules_for_dist(distribution_name: str, distribution_type: DistributionType, modules: set[str]) -> None:
    with extract_distribution(distribution_name) as name:
        assert modules == get_modules_for_dist(distribution_type, name)

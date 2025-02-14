# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()

python_tests(name="tests")

python_awslambda(
    name="dynamodb-to-es-lambda",
    runtime="python3.9",
    dependencies=[":dynamodb_es_bridge"],
    handler="toolchain.buildsense.dynamodb_es_bridge.dynamodb_to_es_lambda:handler",
)

python_test_utils(name="test_utils")

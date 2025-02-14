# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python:psycopg2",
    ],
)

python_tests(name="tests")

pex_binary(name="launch_db_on_kubernetes", entry_point="launch_db_on_kubernetes.py")
pex_binary(name="launch_db_on_local_machine", entry_point="launch_db_on_local_machine.py")
pex_binary(name="dump_postgres_db", entry_point="dump_postgres_db.py")

python_test_utils(name="test_utils")

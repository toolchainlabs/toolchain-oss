# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()


pex_binary(name="notifications-api-manage", entry_point="manage.py", dependencies=[":api"])

pex_binary(name="notifications-api-gunicorn", entry_point="gunicorn_main.py", dependencies=[":api"])

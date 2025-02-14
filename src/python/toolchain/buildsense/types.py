# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
from typing import Union

FieldValue = Union[str, int, list[str], tuple[datetime.timedelta, datetime.timedelta], bool]
FieldsMap = dict[str, FieldValue]

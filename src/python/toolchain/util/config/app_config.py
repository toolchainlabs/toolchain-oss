# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Union

ValueType = Union[str, list, dict]
ConfigDict = dict[str, ValueType]


class AppConfig:
    """Configuration data for django apps.

    The purpose of this class is to create an abstraction layer between the logic in various django setting files and
    the actual location/source of the data which we use to calculate and configure stuff in the django settings files.

    For now, we are only supporting loading those from OS environment variables. The plan is to add support for loading
    the settings from k8s ConfigMaps and from the user's home folder (when running manage.py runserver on the local
    machine).
    """

    CONFIG_FILE = Path("/etc/config/service_config.json")  # See prod/helm/django
    _TRUE_VALUES = {"1", "t", "true"}

    @classmethod
    def from_env(cls):
        return cls(dict(os.environ))

    def __init__(self, config: ConfigDict) -> None:
        self._config = config

    def apply_config_file(self) -> None:
        config = self._load_config_file()
        self._config.update(config)

    def _load_config_file(self) -> ConfigDict:
        config_json = json.loads(self.CONFIG_FILE.read_text())
        config = {}
        for config_section in config_json.values():
            config.update({k.upper(): v for k, v in config_section.items()})
        return config

    def get(self, key: str, default: ValueType | None = None) -> ValueType | None:
        return self._config.get(key, default)

    def get_config_section(self, section: str) -> dict:
        return self.get(key=section, default={})  # type: ignore[return-value]

    def is_set(self, key: str, default: bool = False) -> bool:
        if key in self._config:
            value = self[key]
            if isinstance(value, bool):
                return value
            return value.lower() in self._TRUE_VALUES  # type: ignore[union-attr]
        return default

    def __getitem__(self, key: str) -> ValueType:
        return self._config[key]

    def maybe_int(self, key: str, default: int) -> int:
        value = self.get(key)
        return default if value is None else int(value)  # type: ignore[arg-type]

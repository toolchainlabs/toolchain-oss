# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from pathlib import Path
from unittest import mock

from toolchain.util.config.app_config import AppConfig


class TestAppConfig:
    def test_is_set(self) -> None:
        cfg = AppConfig({"Jerry": "0", "newman": "true", "bania": "false", "mandelbaum": "1"})
        assert cfg.is_set("Jerry", default=True) is False
        assert cfg.is_set("Jerry") is False
        assert cfg.is_set("mandelbaum") is True
        assert cfg.is_set("newman") is True
        assert cfg.is_set("bania", default=True) is False
        assert cfg.is_set("bania") is False
        assert cfg.is_set("cosmo") is False
        assert cfg.is_set("cosmo", default=True) is True

    def test_maybe_int(self) -> None:
        cfg = AppConfig({"jerry": "0928", "kenny": "821"})
        assert cfg.maybe_int("jerry", default=12) == 928
        assert cfg.maybe_int("kenny", default=91) == 821
        assert cfg.maybe_int("gold", default=677) == 677

    def test_get_item(self) -> None:
        cfg = AppConfig({"jerry": "hello", "uncle": "leo"})
        assert cfg["jerry"] == "hello"
        assert cfg["uncle"] == "leo"

    def test_get(self) -> None:
        cfg = AppConfig({"jerry": "hello", "uncle": "leo"})
        assert cfg.get("jerry") == "hello"
        assert cfg.get("jerry", default="cosmo") == "hello"
        assert cfg.get("uncle") == "leo"
        assert cfg.get("uncle", default="cosmo") == "leo"
        assert cfg.get("newman") is None
        assert cfg.get("newman", default="usps") == "usps"

    def test_apply_config_file(self, tmp_path: Path) -> None:
        cfg = AppConfig({"JERRY": "hello", "UNCLE": "leo", "WILHELM": "tanya"})
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "kenny": {"jerry": "gold-jerry-gold", "little": {"jerry": "seinfeld", "dana": "folly"}},
                    "cosmo": {"UNCLE": "newman", "magic": "crepe", "del": ["boca", "vista"]},
                    "app": {"bob": True, "puddy": False},
                }
            )
        )
        with mock.patch("toolchain.util.config.app_config.AppConfig.CONFIG_FILE", new=config_file):
            cfg.apply_config_file()
        assert cfg["WILHELM"] == "tanya"
        assert cfg["JERRY"] == "gold-jerry-gold"
        assert cfg["UNCLE"] == "newman"
        assert cfg["MAGIC"] == "crepe"
        assert cfg["DEL"] == ["boca", "vista"]
        assert cfg["LITTLE"] == {"jerry": "seinfeld", "dana": "folly"}
        assert cfg.is_set("BOB") is True
        assert cfg.is_set("PUDDY") is False
        assert cfg.is_set("DARREN", default=True) is True
        assert cfg.is_set("DAVID") is False

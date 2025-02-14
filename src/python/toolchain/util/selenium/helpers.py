# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from selenium.webdriver import Chrome, ChromeOptions

_CHROME_OPTIONS = ["--disable-dev-shm-usage", "--no-sandbox", "--headless"]


def get_chrome_driver() -> Chrome:
    options = ChromeOptions()
    for opt in _CHROME_OPTIONS:
        options.add_argument(opt)
    return Chrome(options=options)

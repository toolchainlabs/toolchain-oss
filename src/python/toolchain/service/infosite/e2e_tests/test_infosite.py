# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from urllib.parse import urljoin

import pytest
from selenium.webdriver.common.by import By

from toolchain.base.datetime_tools import utcnow
from toolchain.prod.e2e_tests.pytest_runner import run_pytest
from toolchain.util.selenium.helpers import get_chrome_driver


@pytest.fixture(scope="module")
def chrome():
    driver = get_chrome_driver()
    yield driver
    driver.close()


def get_url(is_dev: bool, host: str, path: str) -> str:
    return urljoin(f"http://{host}", path) if is_dev else urljoin(f"https://{host}", path)


def _load_page(driver, host: str, is_dev: bool, path: str) -> None:
    url = get_url(is_dev, host, path)
    print(f"GOING TO {host} -- {url}")
    driver.get(url)
    assert driver.get_log("browser") == []
    if path != "security":
        # Workaround for issue w/ security page since it doesn't have the copyright notice other pages have.
        # should be resloved as part of https://github.com/toolchainlabs/toolchain/issues/14655
        year = utcnow().year
        assert driver.find_element(By.CLASS_NAME, "copyright-txt").text == f"© 2018-{year} Toolchain Labs, Inc."
    return driver


def test_redirect_http(chrome, host: str, is_dev: bool) -> None:
    if is_dev:
        return
    chrome.get(f"http://{host}/")
    assert chrome.current_url == f"https://{host}/"


@pytest.mark.skip(reason="No open jobs currently")
def test_jobs_page(chrome, host: str, is_dev: bool) -> None:
    _load_page(chrome, host, is_dev, "jobs")
    assert chrome.title == "Toolchain Labs | Jobs"


def test_jobs_redirect(chrome, host: str, is_dev: bool) -> None:
    _load_page(chrome, host, is_dev, "jobs")
    assert chrome.title == "Toolchain Labs | Home"


@pytest.mark.parametrize(
    ("path", "expected_title"),
    [
        ("contact", "Toolchain Labs | Contact"),
        ("product", "Toolchain Labs | Product"),
        ("privacy", "Toolchain Labs | Privacy Policy"),
        ("terms", "Toolchain Labs | Terms Of Use"),
        ("about", "Toolchain Labs | About"),
        ("pricing", "Toolchain Labs | Pricing"),
        ("security", "Toolchain Labs | Security"),
        ("", "Toolchain Labs | Home"),
    ],
)
def test_page(chrome, host: str, is_dev: bool, path: str, expected_title: str) -> None:
    _load_page(chrome, host, is_dev, path)
    assert chrome.title == expected_title


def test_404(chrome, host: str, is_dev: bool) -> None:
    url = get_url(is_dev, host, "little-jerry-seinfeld")
    print(f"GOING TO {host} -- {url}")
    chrome.get(url)
    assert len(chrome.get_log("browser")) > 0
    assert chrome.title == "Toolchain Labs | 404"


if __name__ == "__main__":
    run_pytest(__file__)

# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from toolchain.constants import ToolchainEnv
from toolchain.infosite.constants import EXTERNAL_RESOURCES


class TestInfoSiteCSP:
    """This test makes sure links to external resources (scripts, fonts, css, etc...) are HTTPS and that their domains
    are included in the CSP policy header.

    Note these tests don't give a 100% coverage for CSP issues. For example, jquery script includes references to
    fonts.googleapis.com which in turn load fonts from fonts.gstatic.com. Theses hosts are listed in our CSP settings,
    but removing them, won't cause tests to fail.
    """

    def test_csp_scripts(self, client, settings) -> None:
        response = client.get("/")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.title.string == "Toolchain Labs | Home"
        for link in [script["src"] for script in soup.find_all("script") if script.has_attr("src")]:
            if link.startswith(settings.STATIC_URL):
                continue
            url = urlparse(link)
            assert url.scheme == "https", f"HTTPS only links allowed in pages. Found: {link}"
            assert (
                url.netloc in EXTERNAL_RESOURCES["scripts"]
            ), f"External host not included in CSP_SCRIPT_SRC and will not load. {link}"

    def test_csp_styles(self, client, settings) -> None:
        response = client.get("/")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        for link in [link["href"] for link in soup.find_all("link")]:
            if link.startswith(settings.STATIC_URL):
                continue
            url = urlparse(link)
            assert url.scheme == "https", f"HTTPS only links allowed in pages. Found: {link}"
            assert (
                url.netloc in EXTERNAL_RESOURCES["styles"]
            ), f"External host not included in CSP_STYLE_SRC and will not load. {link}"


class TestViews:
    def test_404(self, client) -> None:
        response = client.get("/hello-jerry")
        assert response.status_code == 404
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | 404"

    def test_product(self, client) -> None:
        response = client.get("/product")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | Product"
        sections = soup.find_all("a", attrs={"class": "product-row-title"})
        assert len(sections) == 3
        assert [section.text for section in sections] == [
            "Caching and analytics that accelerate your team’s work",
            "An ergonomic, open-source developer workflow system",
            "Make your builds and workflows stable and efficient",
        ]

    def test_home(self, client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | Home"

    def test_terms(self, client) -> None:
        response = client.get("/terms")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | Terms Of Use"

    def test_privacy_policy(self, client) -> None:
        response = client.get("/privacy")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | Privacy Policy"

    def test_contact(self, client) -> None:
        response = client.get("/contact")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | Contact"
        start_free_button = soup.select("div a.link-button")[0]
        assert start_free_button.attrs["href"] == "https://app.toolchain.com/"
        assert start_free_button.text.strip() == "start free"

    def test_about(self, client) -> None:
        response = client.get("/about")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | About"
        title = soup.select("h1.our-team-title")[0]
        assert title.text.strip() == "Our team"
        team_members = title.parent.select("ul li")
        assert len(team_members) == 9

    def test_robots_txt_prod(self, client, settings) -> None:
        settings.TOOLCHAIN_ENV = ToolchainEnv("toolchain_prod").namespaced(namespace="prod", is_local=False)  # type: ignore[attr-defined]
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert response.content == b"User-agent: *\nDisallow:"

    def test_robots_txt_staging(self, client, settings) -> None:
        settings.TOOLCHAIN_ENV = ToolchainEnv("toolchain_prod").namespaced(namespace="staging", is_local=False)  # type: ignore[attr-defined]
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert response.content == b"User-agent: *\nDisallow: /"

    def test_ads_txt(self, client) -> None:
        response = client.get("/ads.txt")
        assert response.status_code == 200
        assert "toolchain.com" in response.content.decode()

    def test_security_txt(self, client) -> None:
        response = client.get("/.well-known/security.txt")
        assert response.status_code == 200
        assert "Contact: security@toolchain.com" in response.content.decode()

    def test_jobs(self, client) -> None:
        response = client.get("/jobs")
        assert response.status_code == 302
        assert response.url == "/"

    def test_security(self, client) -> None:
        response = client.get("/security")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | Security"

    def test_pricing(self, client) -> None:
        response = client.get("/pricing")
        assert response.status_code == 200
        soup = BeautifulSoup(response.content, "html.parser")
        assert soup.select("title")[0].text == "Toolchain Labs | Pricing"
        tiers = soup.select(".pricing-box")
        assert len(tiers) == 2  # Two tiers
        assert tiers[0].select_one("h2").text == "Starter"
        assert tiers[1].select_one("h2").text == "Enterprise"

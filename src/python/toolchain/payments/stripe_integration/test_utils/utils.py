# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from urllib.parse import ParseResult, parse_qsl, urlparse

import pkg_resources

# also in conftest.py
FAKE_STRIPE_DOMAIN = "https://jerry.not-stripe.fake"


def load_fixture(fixture_name: str):
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json"))


def add_create_customer_response(responses, stripe_id: str | None = None, customer_id: str | None = None) -> None:
    resp = load_fixture("create_customer_response")
    if stripe_id:
        resp["id"] = stripe_id
    if customer_id:
        resp["metadata"]["toolchain_id"] = customer_id
    responses.add(responses.POST, url=f"{FAKE_STRIPE_DOMAIN}/v1/customers", json=resp)


def add_modify_customer_response(responses, stripe_id: str) -> None:
    resp = load_fixture("update_customer_response")
    resp["id"] = stripe_id
    responses.add(responses.POST, url=f"{FAKE_STRIPE_DOMAIN}/v1/customers/{stripe_id}", json=resp)


def add_search_customer_response_items(responses, items: list[dict]):
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/customers/search",
        json={
            "object": "search_result",
            "data": items,
            "has_more": False,
            "next_page": None,
            "url": "/v1/customers/search",
        },
    )


def add_search_customer_response(
    responses,
    stripe_id: str | None = None,
    customer_id: str | None = None,
    billing_email: str | None = None,
    add_default_payment: bool = False,
) -> None:
    fixture = load_fixture("customer_search_response")
    customer_entry = fixture["data"][0]
    if stripe_id:
        customer_entry["id"] = stripe_id
    if customer_id:
        customer_entry["metadata"]["toolchain_id"] = customer_id
    if billing_email:
        customer_entry["email"] = billing_email
    if add_default_payment:
        customer_entry["invoice_settings"]["default_payment_method"] = "pm_1L7nDBEfbv3GSgSdDn3ZidJC"
    add_search_customer_response_items(responses, fixture["data"])


def add_search_customer_empty_response(responses) -> None:
    add_search_customer_response_items(responses, [])


def add_create_customer_portal_session_response(responses):
    responses.add(
        responses.POST,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/billing_portal/sessions",
        json={
            "id": "bps_1KtyOVWCR",
            "object": "billing_portal.session",
            "configuration": "bpc_1Ktyz9wQt",
            "created": 1651256299,
            "customer": "cus_LbAj90jH7vchMD",
            "livemode": True,
            "locale": None,
            "on_behalf_of": None,
            "return_url": "https://example.com/account",
            "url": "https://newman-billing.com/session/no-soup-for-you",
        },
    )


def add_product_and_prices_search_responses(responses) -> None:
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/products/search",
        json=load_fixture("product_search_response"),
    )
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/prices/search",
        json=load_fixture("price_search_response"),
    )


def add_product_and_prices_responses(responses, product_id: str, price_id: str) -> None:
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/products/{product_id}",
        json=load_fixture("product_search_response")["data"][0],
    )
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/prices/{price_id}",
        json=load_fixture("price_search_response")["data"][-1],
    )


def add_list_customer_subscriptions_response(
    responses, empty: bool = False, stripe_customer_id: str | None = None
) -> None:
    if empty:
        fixture = {"object": "list", "data": [], "has_more": False, "url": "/v1/subscriptions"}
    else:
        fixture = load_fixture("list_customer_subscriptions_response")
        if stripe_customer_id:
            fixture["data"][0]["customer"] = stripe_customer_id  # type: ignore[index]
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/subscriptions",
        json=fixture,
    )


def add_create_customer_subscriptions_response(responses, stripe_customer_id: str | None = None) -> None:
    fixture = load_fixture("list_customer_subscriptions_response")["data"][0]
    if stripe_customer_id:
        fixture["customer"] = stripe_customer_id
    responses.add(
        responses.POST,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/subscriptions",
        json=fixture,
    )


def add_get_subscription_response(
    responses,
    subscription_id: str,
    exists: bool = True,
    subscription_status: str | None = None,
    stripe_customer_id: str | None = None,
):
    if exists:
        fixture = load_fixture("get_subscription_response")
        if subscription_status:
            fixture["status"] = subscription_status
        if stripe_customer_id:
            fixture["customer"] = stripe_customer_id
        responses.add(responses.GET, url=f"{FAKE_STRIPE_DOMAIN}/v1/subscriptions/{subscription_id}", json=fixture)
    else:
        responses.add(
            responses.GET,
            url=f"{FAKE_STRIPE_DOMAIN}/v1/subscriptions/{subscription_id}",
            status=404,
            json={
                "error": {
                    "code": "resource_missing",
                    "doc_url": "https://stripe.com/docs/error-codes/resource-missing",
                    "message": f"No such subscription: '{subscription_id}'",
                    "param": "id",
                    "type": "invalid_request_error",
                }
            },
        )


def add_cancel_subscription_response(responses, subscription_id: str) -> None:
    fixture = load_fixture("delete_subscription_response")
    responses.add(responses.DELETE, url=f"{FAKE_STRIPE_DOMAIN}/v1/subscriptions/{subscription_id}", json=fixture)


def assert_stripe_request(request) -> ParseResult:
    assert request.headers["Authorization"] == "Bearer no-soup-for-you"
    url = urlparse(request.url)
    assert url.scheme == "https"
    assert url.netloc == "jerry.not-stripe.fake"
    return url


def assert_customer_search_request(request, env_name: str, toolchain_customer_id: str) -> None:
    assert request.method == "GET"
    url = assert_stripe_request(request)
    assert url.path == "/v1/customers/search"
    assert dict(parse_qsl(url.query)) == {
        "query": f'metadata["toolchain_id"]:"{toolchain_customer_id}" AND metadata["toolchain_env"]:"{env_name}"'
    }


def assert_modify_customer(request, stripe_id: str, billing_email: str) -> None:
    assert request.method == "POST"
    url = assert_stripe_request(request)
    assert url.path == f"/v1/customers/{stripe_id}"
    params = dict(parse_qsl(request.body))
    assert params == {"email": billing_email}


def assert_customer_create_request(
    request, env_name: str, toolchain_customer_id: str, name: str, email: str | None
) -> None:
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    url = assert_stripe_request(request)
    assert url.path == "/v1/customers"
    params = dict(parse_qsl(request.body))
    expected_params = {
        "name": name,
        "metadata[toolchain_id]": toolchain_customer_id,
        "metadata[toolchain_env]": env_name,
    }
    if email:
        expected_params["email"] = email
    assert params == expected_params


def assert_create_customer_portal_session_request(request, stripe_customer_id: str, return_url: str) -> None:
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    url = assert_stripe_request(request)
    assert url.path == "/v1/billing_portal/sessions"
    params = dict(parse_qsl(request.body))
    assert params == {"customer": stripe_customer_id, "return_url": return_url}


def assert_product_search_request(request):
    assert request.method == "GET"
    url = assert_stripe_request(request)
    assert url.path == "/v1/products/search"
    assert dict(parse_qsl(url.query)) == {"query": 'active:"true" AND metadata["TOOLCHAIN_DEFAULT_PLAN"]:"True"'}


def assert_price_search_request(request, product_id: str = "prod_LcgVoYRbtZeS7i"):
    assert request.method == "GET"
    url = assert_stripe_request(request)
    assert url.path == "/v1/prices/search"
    assert dict(parse_qsl(url.query)) == {"query": f'active:"true" AND product:"{product_id}"'}


def assert_product_retrieve_request(request, product_id: str):
    assert request.method == "GET"
    url = assert_stripe_request(request)
    assert url.path == f"/v1/products/{product_id}"
    assert url.query == ""


def assert_price_retrieve_request(request, price_id: str):
    assert request.method == "GET"
    url = assert_stripe_request(request)
    assert url.path == f"/v1/prices/{price_id}"
    assert url.query == ""


def assert_list_customer_subscriptions_request(request, stripe_customer_id: str) -> None:
    assert request.method == "GET"
    url = assert_stripe_request(request)
    assert url.path == "/v1/subscriptions"
    assert dict(parse_qsl(url.query)) == {"customer": stripe_customer_id}


def assert_create_customer_subscriptions_request(
    request,
    toolchain_customer_id: str,
    stripe_customer_id: str,
    price_id: str,
    trial_period_days: int,
    billing_anchor_ts: int,
    tc_env_name: str = "test",
) -> None:
    assert request.method == "POST"
    url = assert_stripe_request(request)
    assert url.path == "/v1/subscriptions"
    assert url.query == ""
    assert dict(parse_qsl(request.body)) == {
        "customer": stripe_customer_id,
        "items[0][price]": price_id,
        "metadata[toolchain_id]": toolchain_customer_id,
        "metadata[toolchain_env]": tc_env_name,
        "trial_period_days": str(trial_period_days),
        "billing_cycle_anchor": str(billing_anchor_ts),
    }


def assert_get_subscriptions_request(request, subscription_id: str) -> None:
    assert request.method == "GET"
    url = assert_stripe_request(request)
    assert url.path == f"/v1/subscriptions/{subscription_id}"
    assert url.query == ""


def assert_cancel_subscriptions_request(request, subscription_id: str) -> None:
    assert request.method == "DELETE"
    url = assert_stripe_request(request)
    assert url.path == f"/v1/subscriptions/{subscription_id}"
    assert url.query == ""

# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest
from stripe.error import InvalidRequestError

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.payments.stripe_integration.stripe_client import (
    StripeCustomersClient,
    get_default_stripe_product,
    get_product_and_price_info,
)
from toolchain.payments.stripe_integration.test_utils.utils import (
    FAKE_STRIPE_DOMAIN,
    add_cancel_subscription_response,
    add_create_customer_portal_session_response,
    add_create_customer_response,
    add_create_customer_subscriptions_response,
    add_get_subscription_response,
    add_list_customer_subscriptions_response,
    add_modify_customer_response,
    add_product_and_prices_responses,
    add_product_and_prices_search_responses,
    add_search_customer_empty_response,
    add_search_customer_response,
    add_search_customer_response_items,
    assert_cancel_subscriptions_request,
    assert_create_customer_portal_session_request,
    assert_create_customer_subscriptions_request,
    assert_customer_create_request,
    assert_customer_search_request,
    assert_get_subscriptions_request,
    assert_list_customer_subscriptions_request,
    assert_modify_customer,
    assert_price_retrieve_request,
    assert_price_search_request,
    assert_product_retrieve_request,
    assert_product_search_request,
    load_fixture,
)


class TestStripeCustomersClient:
    @pytest.fixture()
    def client(self) -> StripeCustomersClient:
        return StripeCustomersClient(toolchain_env_name="jerry")

    def test_create_client_invalid_env(self) -> None:
        with pytest.raises(ToolchainAssertion, match="toolchain_env_name can't be empty."):
            StripeCustomersClient(toolchain_env_name="")

    def test_get_customer_by_toolchain_id(self, responses, client: StripeCustomersClient) -> None:
        add_search_customer_response(responses)
        customer = client.get_customer_by_toolchain_id(toolchain_customer_id="george")
        assert customer is not None
        assert customer.name == "jerry test 1"
        assert customer.stripe_id == "cus_La28SpSIkT9BDh"
        assert customer.toolchain_id == "jerryjerryjerry8323"
        assert len(responses.calls) == 1
        assert_customer_search_request(responses.calls[0].request, "jerry", toolchain_customer_id="george")

    def test_get_customer_by_toolchain_id_not_found(self, responses, client: StripeCustomersClient) -> None:
        add_search_customer_empty_response(responses)
        assert client.get_customer_by_toolchain_id(toolchain_customer_id="kramer") is None
        assert len(responses.calls) == 1
        assert_customer_search_request(responses.calls[0].request, "jerry", toolchain_customer_id="kramer")

    def test_get_customer_by_toolchain_id_multiple_customers(self, responses, client: StripeCustomersClient) -> None:
        customer_data = load_fixture("customer_search_response")["data"][0]
        add_search_customer_response_items(responses, items=[customer_data, customer_data, customer_data])
        with pytest.raises(
            ToolchainAssertion, match="More than one stripe customer object with toolchain id: davola - 3"
        ):
            client.get_customer_by_toolchain_id(toolchain_customer_id="davola")
        assert len(responses.calls) == 1
        assert_customer_search_request(responses.calls[0].request, "jerry", toolchain_customer_id="davola")

    def test_get_or_create_customer_new_customer(self, responses, client: StripeCustomersClient) -> None:
        add_search_customer_empty_response(responses)
        add_create_customer_response(responses)
        customer, created = client.get_or_create_customer(
            name="NBC", toolchain_customer_id="newman", billing_email="bob@festivus.com"
        )
        assert created is True
        assert customer.name == "jerry test 2"
        assert customer.stripe_id == "cus_La460IqvH5UIJa"
        assert customer.toolchain_id == "kramerkramer878373"
        assert customer.billing_email == "kramer@festivus.org"
        assert customer.has_default_payment_method is False
        assert len(responses.calls) == 2
        assert_customer_search_request(responses.calls[0].request, "jerry", toolchain_customer_id="newman")
        assert_customer_create_request(
            responses.calls[1].request, "jerry", toolchain_customer_id="newman", name="NBC", email="bob@festivus.com"
        )

    def test_update_customer_billing_email(self, responses, client: StripeCustomersClient) -> None:
        add_modify_customer_response(responses, stripe_id="newman")
        client.update_customer_billing_email(stripe_customer_id="newman", billing_email="bob@festivus.com")
        assert len(responses.calls) == 1
        assert_modify_customer(responses.calls[0].request, stripe_id="newman", billing_email="bob@festivus.com")

    def test_get_or_create_customer_exits_customer(self, responses, client: StripeCustomersClient) -> None:
        add_search_customer_response(responses, add_default_payment=True)
        customer, created = client.get_or_create_customer(
            name="NBC", toolchain_customer_id="elaine", billing_email="david.puddy@saab.com"
        )
        assert created is False
        assert customer.name == "jerry test 1"
        assert customer.stripe_id == "cus_La28SpSIkT9BDh"
        assert customer.toolchain_id == "jerryjerryjerry8323"
        assert customer.billing_email is None
        assert customer.has_default_payment_method is True
        assert len(responses.calls) == 1
        assert_customer_search_request(responses.calls[0].request, "jerry", toolchain_customer_id="elaine")

    @pytest.mark.parametrize(
        ("name", "tc_id"),
        [
            ("", ""),
            ("", "puddy"),
            ("kramer", ""),
        ],
    )
    def test_get_or_create_customer_invalid_call(
        self, responses, client: StripeCustomersClient, name: str, tc_id: str
    ) -> None:
        add_search_customer_empty_response(responses)
        with pytest.raises(ToolchainAssertion, match="Invalid args for customer creation."):
            client.get_or_create_customer(name=name, toolchain_customer_id=tc_id, billing_email="kramer@festivus.ai")
        assert len(responses.calls) == 1
        assert_customer_search_request(responses.calls[0].request, "jerry", toolchain_customer_id=tc_id)

    def test_create_customer_portal_session(self, responses, client: StripeCustomersClient) -> None:
        add_create_customer_portal_session_response(responses)
        session_url = client.create_customer_portal_session(
            stripe_customer_id="joe_davola", return_url="https://elaine-mail.com/nbc/"
        )
        assert session_url == "https://newman-billing.com/session/no-soup-for-you"
        assert len(responses.calls) == 1
        assert_create_customer_portal_session_request(
            responses.calls[0].request, stripe_customer_id="joe_davola", return_url="https://elaine-mail.com/nbc/"
        )

    def test_get_customer_subscriptions(self, responses, client: StripeCustomersClient) -> None:
        add_list_customer_subscriptions_response(responses)
        subscriptions = client.get_customer_subscriptions(stripe_customer_id="joe_davola")
        assert len(subscriptions) == 1
        assert subscriptions[0].status == "trialing"
        assert subscriptions[0].stripe_customer_id == "cus_feats_of_strength"
        assert subscriptions[0].stripe_id == "sub_jambalaya_soup"

        assert len(responses.calls) == 1
        assert_list_customer_subscriptions_request(responses.calls[0].request, stripe_customer_id="joe_davola")

    def test_create_trial_subscription(self, responses, client: StripeCustomersClient) -> None:
        add_create_customer_subscriptions_response(responses)
        subscription = client.create_trial_subscription(
            toolchain_customer_id="david_puddy",
            stripe_customer_id="joe_davola",
            price_id="jacket",
            trial_period_days=24,
            billing_anchor=datetime.date(2023, 8, 3),
        )
        assert subscription.status == "trialing"
        assert subscription.stripe_customer_id == "cus_feats_of_strength"
        assert subscription.stripe_id == "sub_jambalaya_soup"
        assert subscription.price_id == "price_1KvR8PEfbv3GSgSdnaXqkFUF"
        assert subscription.product_id == "prod_LcgVoYRbtZeS7i"
        assert subscription.is_active is False
        assert subscription.is_trial is True
        assert subscription.is_limited is False
        assert len(responses.calls) == 1
        assert_create_customer_subscriptions_request(
            responses.calls[0].request,
            toolchain_customer_id="david_puddy",
            stripe_customer_id="joe_davola",
            price_id="jacket",
            trial_period_days=24,
            tc_env_name="jerry",
            billing_anchor_ts=1691020800,
        )

    def test_get_subscription(self, responses, client: StripeCustomersClient) -> None:
        add_get_subscription_response(responses, subscription_id="joe_davola")
        subscription = client.get_subscription("joe_davola")
        assert len(responses.calls) == 1
        assert_get_subscriptions_request(responses.calls[0].request, "joe_davola")
        assert subscription.status == "trialing"
        assert subscription.stripe_id == "sub_1L6dslEfbv3GSgSdlcN25ytd"
        assert subscription.stripe_customer_id == "cus_Lcefu2imyafNUv"
        assert subscription.price_id == "price_1KvR8PEfbv3GSgSdnaXqkFUF"
        assert subscription.product_id == "prod_LcgVoYRbtZeS7i"
        assert subscription.start_date == datetime.date(2022, 6, 3)
        assert subscription.trial_end == datetime.date(2022, 7, 3)
        assert subscription.is_active is False
        assert subscription.is_trial is True
        assert subscription.is_limited is False

    def test_get_subscription_doesnt_exist(self, responses, client: StripeCustomersClient) -> None:
        add_get_subscription_response(responses, subscription_id="joe_davola", exists=False)
        with pytest.raises(InvalidRequestError, match="No such subscription: 'joe_davola'"):
            client.get_subscription("joe_davola")
        assert len(responses.calls) == 1
        assert_get_subscriptions_request(responses.calls[0].request, "joe_davola")

    def test_cancel_subscription(self, responses, client: StripeCustomersClient) -> None:
        add_cancel_subscription_response(responses, subscription_id="crazy_joe_davola")
        client.cancel_subscription("crazy_joe_davola")
        assert len(responses.calls) == 1
        assert_cancel_subscriptions_request(responses.calls[0].request, "crazy_joe_davola")


def test_get_default_stripe_product(responses) -> None:
    add_product_and_prices_search_responses(responses)
    product = get_default_stripe_product()
    assert product.product_id == "prod_LcgVoYRbtZeS7i"
    assert product.price_id == "price_no_bagel_no_bagel_no_bagel"
    assert product.price_nick_name == "Cinnamon Babka"
    assert product.product_name == "Kramer"
    assert product.product_description == "Basic plan, mostly physical comedy."
    assert product.monthly_usd_cost == 20
    assert len(responses.calls) == 2
    assert_product_search_request(responses.calls[0].request)
    assert_price_search_request(responses.calls[1].request)


def test_get_product_and_price_info(responses) -> None:
    add_product_and_prices_responses(responses, product_id="festivus", price_id="costanza")
    product = get_product_and_price_info(product_id="festivus", price_id="costanza")
    assert product.product_id == "prod_LcgVoYRbtZeS7i"
    assert product.price_id == "price_no_bagel_no_bagel_no_bagel"
    assert product.price_nick_name == "Cinnamon Babka"
    assert product.product_name == "Kramer"
    assert product.product_description == "Basic plan, mostly physical comedy."
    assert product.monthly_usd_cost == 20
    assert len(responses.calls) == 2
    assert_product_retrieve_request(responses.calls[0].request, product_id="festivus")
    assert_price_retrieve_request(responses.calls[1].request, price_id="costanza")


def test_get_product_and_price_info_mismatch(responses) -> None:
    fixture = load_fixture("product_search_response")["data"][0]
    fixture["id"] = "worlds_collide"
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/products/jerry",
        json=fixture,
    )
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/prices/susan",
        json=load_fixture("price_search_response")["data"][0],
    )
    with pytest.raises(ToolchainAssertion, match="price_1KvnUvEfbv3GSgSdPOLuyFxJ - Jackie Chiles is not under product"):
        get_product_and_price_info(product_id="jerry", price_id="susan")
    assert len(responses.calls) == 2
    assert_product_retrieve_request(responses.calls[0].request, product_id="jerry")
    assert_price_retrieve_request(responses.calls[1].request, price_id="susan")


def test_get_product_and_price_info_invalid_price(responses) -> None:
    fixture = load_fixture("product_search_response")["data"][0]
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/products/jerry",
        json=fixture,
    )
    responses.add(
        responses.GET,
        url=f"{FAKE_STRIPE_DOMAIN}/v1/prices/susan",
        json=load_fixture("price_search_response")["data"][0],
    )
    with pytest.raises(ToolchainAssertion, match="Unexpected price internval"):
        get_product_and_price_info(product_id="jerry", price_id="susan")
    assert len(responses.calls) == 2
    assert_product_retrieve_request(responses.calls[0].request, product_id="jerry")
    assert_price_retrieve_request(responses.calls[1].request, price_id="susan")

# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.forms import CharField, IntegerField

from toolchain.django.forms.base_form import ToolchainForm


class DummyForm(ToolchainForm):
    jerry = CharField(required=False)
    cosmo = IntegerField(required=False)


class FestivusForm(ToolchainForm):
    allow_unexpected_fields = True
    frank = CharField(required=True)
    estelle = IntegerField(required=False)


def test_error_on_unexpected_fields():
    form = DummyForm({"george": "constanza"})
    assert form.is_valid() is False
    assert form.errors.get_json_data() == {
        "__all__": [{"code": "unexpected", "message": "Got unexpected fields: george"}]
    }

    form = DummyForm({"george": "constanza", "cosmo": "not-a-number"})
    assert form.is_valid() is False
    assert form.errors.get_json_data() == {
        "__all__": [{"code": "unexpected", "message": "Got unexpected fields: george"}],
        "cosmo": [{"code": "invalid", "message": "Enter a whole number."}],
    }


def test_no_error_on_unexpected_fields():
    form = FestivusForm({"george": "constanza", "frank": "tinsel"})
    assert form.is_valid() is True


def test_form_django_errors():
    form = DummyForm({"cosmo": "not-a-number"})
    assert form.is_valid() is False
    assert form.errors.get_json_data() == {"cosmo": [{"code": "invalid", "message": "Enter a whole number."}]}


def test_form_valid_form():
    form = DummyForm({"cosmo": "33"})
    assert form.is_valid() is True
    assert form.errors.get_json_data() == {}
    assert form.cleaned_data["cosmo"] == 33
    assert form.cleaned_data["jerry"] == ""

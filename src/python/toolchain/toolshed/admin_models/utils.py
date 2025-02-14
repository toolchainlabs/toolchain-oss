# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

from django.contrib.admin import ModelAdmin, SimpleListFilter
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer

from toolchain.django.site.models import Customer


def pretty_format_json(json_data: str | bytes | dict) -> str:
    if isinstance(json_data, (str, bytes)):
        json_data = json.loads(json_data)
    # Based on https://www.pydanny.com/pretty-formatting-json-django-admin.html
    response = json.dumps(json_data, sort_keys=True, indent=2)
    formatter = HtmlFormatter(style="colorful")
    response = highlight(response, JsonLexer(), formatter)
    style = "<style>" + formatter.get_style_defs() + "</style><br>"
    # Safe the output
    return mark_safe(style + response)  # nosec: B703, B308


def url_as_link(url: str, text: str | None = None) -> str:
    return format_html("<a target='_blank' href='{url}'>{text}</a>", url=url, text=text or url)


class ReadOnlyModelAdmin(ModelAdmin):
    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


# Based on https://stackoverflow.com/a/16556771/38265
class EnumListFilterWithDefault(SimpleListFilter):
    def lookups(self, request, model_admin):
        return ((None, self.default_value_title),) + self.get_enum_choices() + (("all", "All"),)

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == lookup,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}, []),
                "display": title,
            }

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            fields = {self.db_field_name: self.default_value.value}
        elif value != "all":
            fields = {self.db_field_name: value}
        else:
            fields = {}
        if fields:
            queryset = queryset.filter(**fields)
        return queryset


def get_link_to_user(user_api_id: str, display: str | None = None) -> str:
    # Works with ToolchainUserAdmin.get_object
    url_path = reverse("users-admin:site_toolchainuser_change", kwargs={"object_id": user_api_id})
    return get_link(url_path, display or user_api_id)


def get_link_to_customer(customer_id: str, display: str | None = None) -> str:
    url_path = reverse("users-admin:site_customer_change", kwargs={"object_id": customer_id})
    return get_link(url_path, display or customer_id)


def get_link(url_path: str, display: str) -> str:
    return format_html(f"<a href={url_path}>{display}</a>")


def get_customer_str(customer: Customer) -> str:
    return f"{customer.slug} ({customer.name})"

# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from string import capwords

import pkg_resources
from csp.decorators import csp_exempt
from django.http.response import HttpResponse
from django.utils.cache import patch_cache_control
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView

from toolchain.base.datetime_tools import utcnow

_ADS_TXT = pkg_resources.resource_string(__name__, "ads.txt")

# Since we use in memory cache (no external cache) this caches the page
# for the lifetime of the pod... assuming the pod lives less than a year, which is reasonable.
PAGE_TEMPLATE_CACHE_TIMEOUT = datetime.timedelta(days=360).total_seconds()


def load_team_data() -> list[dict]:
    team = json.loads(pkg_resources.resource_string(__name__, "team.json"))["toolchain_team"]
    for member in team:
        alias = member["alias"]
        member["headshot"] = f"infosite/images/headshots/{alias}-headshot_v2.webp"
    return team


@method_decorator(cache_page(timeout=PAGE_TEMPLATE_CACHE_TIMEOUT), name="get")
class InfositeTemplateView(TemplateView):
    view_type = "app"
    add_meta_tags = False
    page_name = ""
    MAX_AGE = int(datetime.timedelta(hours=3).total_seconds())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(copyright_year=utcnow().year, add_meta_tags=self.add_meta_tags, page_name=self.page_name)
        return context

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        patch_cache_control(response, max_age=self.MAX_AGE)
        return response


def get_infosite_template_view(template_name: str, add_meta_tags: bool = False):
    return InfositeTemplateView.as_view(
        template_name=f"infosite/{template_name}.html",
        page_name=capwords(template_name.replace("_", " ")),
        add_meta_tags=add_meta_tags,
    )


class AboutUsView(InfositeTemplateView):
    TEAM = load_team_data()
    add_meta_tags = True
    template_name = "infosite/about.html"
    page_name = "About"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["team_members"] = self.TEAM
        return context


class PricingView(InfositeTemplateView):
    add_meta_tags = True
    template_name = "infosite/pricing.html"
    page_name = "Pricing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["get_started_toolchain_link"] = "https://app.toolchain.com/auth/login/"
        return context


class PageNotFound(TemplateView):
    template_name = "infosite/404.html"
    view_type = "app"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context, status=404)


@csp_exempt
def ads_txt(request):
    return HttpResponse(content=_ADS_TXT, content_type="text/plain")


ads_txt.view_type = "app"

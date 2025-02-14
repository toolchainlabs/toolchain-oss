# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import re_path

from toolchain.crawler.base.models import FetchURL
from toolchain.workflow.admin_views import WorkflowDetailsView


class WorkUnitDetailBase(WorkflowDetailsView):
    @staticmethod
    def fetchurl_detail_url(web_resource):
        """Returns the URL of the details page of the FetchURL work that fetched the specified web resource.

        If we don't have those details, just use the WebResource's details URL directly.
        """
        fetch_url = FetchURL.get_or_none(web_resource_id=web_resource.id)
        return fetch_url.get_absolute_url() if fetch_url else web_resource.url


class FetchURLDetail(WorkUnitDetailBase):
    model = FetchURL
    template_name = "crawler/fetchurl_detail.html"

    def get_context_data(self, **kwargs):
        fetch_url = kwargs["object"]
        web_resource = fetch_url.web_resource
        context = super().get_context_data(**kwargs)
        if web_resource:
            # We only use these context keys in the template if the fetch was successful.
            context.update(
                {
                    "web_resource": web_resource,
                    "text_content": web_resource.get_content_as_text() if web_resource.is_text else "N/A (binary data)",
                }
            )
        return context


def get_base_crawler_urls(db_name: str):
    base_crawler_urls = [
        re_path(r"^fetchurl/(?P<pk>\d+)/$", FetchURLDetail.as_view(db_name=db_name), name="fetchurl_detail")
    ]
    return base_crawler_urls, "crawler_base"

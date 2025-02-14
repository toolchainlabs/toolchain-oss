# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, re_path, reverse

from toolchain.crawler.base.views import WorkUnitDetailBase, get_base_crawler_urls
from toolchain.crawler.pypi import models
from toolchain.workflow.admin_views import LinksDict


class PypiCrawlerDetailsView(WorkUnitDetailBase):
    pass


class ProcessAllProjectsDetail(PypiCrawlerDetailsView):
    model = models.ProcessAllProjects

    template_name = "crawler/processallprojects_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shards = []
        for shard in kwargs["object"].shards.order_by("shard_number"):
            shard.process_by_shard_link = reverse(
                "crawler_pypi:processallprojectsshard_detail", kwargs={"pk": shard.pk}
            )
        context["shards"] = shards
        return context


class ProcessAllProjectsShardDetail(PypiCrawlerDetailsView):
    model = models.ProcessAllProjectsShard

    template_name = "crawler/processallprojectsshard_detail.html"

    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        process_all_projects_shard = kwargs["object"]
        links.update(
            {
                "processallprojects_detail": reverse(
                    "crawler:processallprojects_detail",
                    kwargs={"pk": process_all_projects_shard.process_all_projects_id},
                )
            }
        )
        return links


class ProcessProjectDetail(PypiCrawlerDetailsView):
    model = models.ProcessProject

    template_name = "crawler/processproject_detail.html"

    def get_links(self, **kwargs) -> LinksDict:
        process_project = kwargs["object"]
        links = super().get_links(**kwargs)
        links.update(
            {"project_link": reverse("pypi:project_detail_by_name", kwargs={"name": process_project.project_name})}
        )
        return links


class ProcessDistributionDetail(PypiCrawlerDetailsView):
    model = models.ProcessDistribution

    template_name = "crawler/processdistribution_detail.html"


class PeriodicallyProcessChangelogDetail(PypiCrawlerDetailsView):
    model = models.PeriodicallyProcessChangelog

    template_name = "crawler/periodicallyprocesschangelog_detail.html"


class ProcessChangelogDetail(PypiCrawlerDetailsView):
    model = models.ProcessChangelog

    template_name = "crawler/processchangelog_detail.html"


class DumpDistributionDataDetail(PypiCrawlerDetailsView):
    model = models.DumpDistributionData

    template_name = "crawler/dumpdistributiondata_detail.html"


def get_pypi_crawler_urls(db_name: str):
    pypi_crawler_urls = [
        re_path(r"^base/", include(get_base_crawler_urls(db_name))),
        # WorkUnit detail views.
        re_path(
            r"^processallprojects/(?P<pk>\d+)/$",
            ProcessAllProjectsDetail.as_view(db_name=db_name),
            name="processallprojects_detail",
        ),
        re_path(
            r"^processallprojectsshard/(?P<pk>\d+)/$",
            ProcessAllProjectsShardDetail.as_view(db_name=db_name),
            name="processallprojectsshard_detail",
        ),
        re_path(
            r"^processproject/(?P<pk>\d+)/$",
            ProcessProjectDetail.as_view(db_name=db_name),
            name="processproject_detail",
        ),
        re_path(
            r"^processdistribution/(?P<pk>\d+)/$",
            ProcessDistributionDetail.as_view(db_name=db_name),
            name="processdistribution_detail",
        ),
        re_path(
            r"^periodicallyprocesschangelog/(?P<pk>\d+)/$",
            PeriodicallyProcessChangelogDetail.as_view(db_name=db_name),
            name="periodicallyprocesschangelog_detail",
        ),
        re_path(
            r"^processchangelog/(?P<pk>\d+)/$",
            ProcessChangelogDetail.as_view(db_name=db_name),
            name="processchangelog_detail",
        ),
        re_path(
            r"^dumpdistributiondata/(?P<pk>\d+)/$",
            DumpDistributionDataDetail.as_view(db_name=db_name),
            name="dumpdistributiondata_detail",
        ),
    ]
    return pypi_crawler_urls

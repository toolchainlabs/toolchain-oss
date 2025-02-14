# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path, reverse

from toolchain.django.db.qs_util import get_rows_and_total_size
from toolchain.packagerepo.pypi.models import Distribution, Project, Release
from toolchain.workflow.admin_views import (
    LinksDict,
    WorkflowAjaxView,
    WorkflowDetailsView,
    WorkflowTemplateView,
    WorkflowView,
)


class PackagerepoViewMixin(WorkflowView):
    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        links.update({"projects": reverse("pypi:projects")})
        return links


class DistributionDetail(WorkflowDetailsView, PackagerepoViewMixin):
    model = Distribution

    template_name = "pypi/distribution_detail.html"


class ReleaseDetail(WorkflowDetailsView, PackagerepoViewMixin):
    model = Release

    template_name = "pypi/release_detail.html"


class ProjectDetail(WorkflowDetailsView, PackagerepoViewMixin):
    model = Project
    slug_field = "name"
    slug_url_kwarg = "name"

    template_name = "pypi/project_detail.html"


class ProjectList(WorkflowTemplateView, PackagerepoViewMixin):
    template_name = "pypi/project_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = Project.objects.all()
        projects = sorted(qs, key=lambda project: project.name)
        for project in projects:
            project.details_link = reverse("pypi:project_detail", kwargs={"pk": project.pk})
        context["projects"] = projects
        return context

    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        links.update({"projects_data": reverse("pypi:projects_data")})
        return links


class ProjectListData(WorkflowAjaxView):
    def get_ajax_data(self):
        search = self.request.GET.get("search")
        offset = int(self.request.GET.get("offset", 0))
        limit = int(self.request.GET.get("limit", 25))
        sort = self.request.GET.get("sort")
        order = self.request.GET.get("order")

        sort_field = "name" if sort == "name" else None

        if sort_field and order == "desc":
            sort_field = f"-{sort_field}"

        workunits_qs = Project.objects.all()
        if sort_field:
            workunits_qs = workunits_qs.order_by(sort_field)
        if search:
            workunits_qs = workunits_qs.filter(name__startswith=search)

        workunit_fields = ["pk", "name"]
        workunits_qs = workunits_qs.values(*workunit_fields)
        workunit_dicts, total = get_rows_and_total_size(workunits_qs, offset, limit)
        ret = {"rows": workunit_dicts, "total": total}
        return ret


def get_pypi_package_repo_urls(db_name: str):
    pypi_package_repo_urls = [
        path("projects/", ProjectList.as_view(db_name=db_name), name="projects"),
        path("projects/data/", ProjectListData.as_view(db_name=db_name), name="projects_data"),
        path("project/<int:pk>/", ProjectDetail.as_view(db_name=db_name), name="project_detail"),
        path("project/<slug:name>/", ProjectDetail.as_view(db_name=db_name), name="project_detail_by_name"),
        path("release/<slug:pk>/", ReleaseDetail.as_view(db_name=db_name), name="release_detail"),
        path("distribution/<slug:pk>/", DistributionDetail.as_view(db_name=db_name), name="distribution_detail"),
    ]
    return pypi_package_repo_urls

# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict
from threading import Thread
from typing import Optional

from django.db.models import Model, Q
from django.http import JsonResponse
from django.urls import path, reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from toolchain.base.datetime_tools import seconds_from_now, utcnow
from toolchain.django.db.qs_util import get_rows_and_total_size
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.util.view_util import AjaxView
from toolchain.toolshed.util.view_util import SuperuserOnlyMixin
from toolchain.workflow.models import WorkExceptionLog, WorkUnit, WorkUnitStateCount

logger = logging.getLogger(__name__)
transaction = TransactionBroker("workflow")

LinksDict = dict[str, Optional[str]]


class WorkflowView(SuperuserOnlyMixin):
    view_type = "admin"
    _VIEW_NAMES = ["summary", "workunit_list", "workexceptionlog_list"]
    db_name = None

    def __init__(self, *args, **kwargs):
        self.db_name = kwargs.pop("db_name")
        super().__init__(*args, **kwargs)

    def _reverse(self, view_name: str, obj_or_kwargs: dict | Model | None = None) -> str:
        namespace = f"workflow-{self.db_name}" if self.db_name else "workflow"
        if not obj_or_kwargs:
            return reverse(f"{namespace}:{view_name}")
        kwargs = obj_or_kwargs if isinstance(obj_or_kwargs, dict) else {"pk": obj_or_kwargs.pk}
        return reverse(f"{namespace}:{view_name}", kwargs=kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"views_links": self.get_links(**kwargs), "db_name": self.db_name})
        return context

    def get_links(self, **kwargs) -> LinksDict:
        return {view_name: self._reverse(view_name) for view_name in self._VIEW_NAMES}


class WorkflowTemplateView(WorkflowView, TemplateView):
    pass


class WorkflowAjaxView(WorkflowView, AjaxView):
    pass


class WorkflowDetailsView(WorkflowView, DetailView):
    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        links.update({"mark_as_feasible": self._reverse("mark_as_feasible")})
        return links


# Views for the admin/toolshed service.


class WorkflowSummary(WorkflowTemplateView):
    template_name = "workflow/summary.html"
    _SUB_VIEWS = ["workunit_stats", "workunit_stats_recompute", "workunit_active_data"]

    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        links.update({view_name: self._reverse(view_name) for view_name in self._SUB_VIEWS})
        return links


class WorkUnitStatsData(WorkflowAjaxView):
    returns_list = True

    def get_ajax_data(self):
        count_by_model = WorkUnitStateCount.get_counts_by_model_and_state()
        return [dict([("ctype__model", k)] + list(v.items())) for k, v in count_by_model.items()]


class WorkUnitStatsRecompute(WorkflowView, View):
    """If the counts ever get out of sync due to some bug, this view will recompute them from raw work unit counts."""

    def post(self, request, *args, **kwargs):
        t = Thread(target=WorkUnitStateCount.recompute, name="RecomputeWorkUnitStats")
        t.start()
        return JsonResponse({})


# WorkUnit views.


class WorkUnitList(WorkflowTemplateView):
    template_name = "workflow/workunit_list.html"

    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        links.update(
            {
                "mark_as_feasible": self._reverse("mark_as_feasible"),
                "workunit_list_data": self._reverse("workunit_list_data"),
            }
        )
        return links


class WorkUnitStatus(WorkflowDetailsView):
    model = WorkUnit

    template_name = "workflow/workunit_status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workunit = kwargs["object"]
        leased_until = workunit.leased_until
        context.update(
            lease_remaining=leased_until - utcnow() if leased_until else None,
            description=workunit.description or workunit.payload.description,
        )
        return context

    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        workunit = kwargs["object"]
        payload = workunit.payload
        payload_url = hasattr(payload, "get_absolute_url") and payload.get_absolute_url()
        links.update(
            {
                "workunit_ancestors": self._reverse("workunit_ancestors", workunit),
                "workunit_descendants": self._reverse("workunit_descendants", workunit),
                "workunit_requirements_data": self._reverse("workunit_requirements_data"),
                "workunit_required_by_data": self._reverse("workunit_required_by_data"),
                "workunit_created_data": self._reverse("workunit_created_data"),
                "workexceptionsforworkunit_data": self._reverse("workexceptionsforworkunit_data"),
                "mark_as_feasible": self._reverse("mark_as_feasible"),
                "payload_url": payload_url or None,
            }
        )
        return links


class WorkUnitListDataBase(WorkflowAjaxView):
    _WORKUNIT_FIELDS = [
        "pk",
        "state",
        "num_unsatisfied_requirements",
        "last_attempt",
        "succeeded_at",
        "leased_until",
        "lease_holder",
        "node",
    ]

    def get_workunit_list_qs(self):
        raise NotImplementedError()

    def _get_descriptions(self, workunits) -> dict[int, str]:
        # groups work unit IDs by payload type and then does one query for each
        # payload type to get descriptions for those payloads.
        types_to_ids = defaultdict(list)
        id_to_desc = {}
        for wu in workunits:
            if wu.description:
                id_to_desc[wu.id] = wu.description
            else:
                types_to_ids[wu.payload_ctype].append(wu.id)
        for ctype, wu_ids in types_to_ids.items():
            for payload in ctype.model_class().objects.filter(work_unit_id__in=wu_ids):
                id_to_desc[payload.work_unit_id] = payload.description
        return id_to_desc

    def get_ajax_data(self):
        search = self.request.GET.get("search")
        offset = int(self.request.GET.get("offset", 0))
        limit = int(self.request.GET.get("limit", 25))
        sort = self.request.GET.get("sort")
        order = self.request.GET.get("order")

        if sort == "type":
            sort_field = "payload_model"
        elif sort == "leased_remaining":
            sort_field = "leased_until"
        elif sort == "state_str":
            sort_field = "state"
        else:
            sort_field = sort
        if order == "desc":
            sort_field = f"-{sort_field}"

        workunits_qs = self.get_workunit_list_qs().select_related("payload_ctype")
        if sort_field:
            workunits_qs = workunits_qs.order_by(sort_field)
        if search:
            search = search.replace("/", " ")
            workunits_qs = workunits_qs.filter(search_vector=search)
        workunits, total = get_rows_and_total_size(workunits_qs, offset, limit)

        descriptions = self._get_descriptions(workunits)
        workunit_dicts = []
        for wu in workunits:
            wd = {field: getattr(wu, field) for field in self._WORKUNIT_FIELDS}
            wd.update(
                {
                    "payload_model": wu.payload_ctype.model,
                    "leased_remaining": seconds_from_now(wu.leased_until),
                    "state_str": wu.state_str(),
                    "status_link": self._reverse("workunit_status", {"pk": wu.pk}),
                    "description": descriptions[wu.id],
                }
            )
            workunit_dicts.append(wd)
        ret = {"rows": workunit_dicts, "total": total}
        return ret

    def get_work_unit(self) -> WorkUnit:
        pk = int(self.request.GET["pk"])  # type: ignore[attr-defined]
        return WorkUnit.objects.get(pk=pk)


class WorkUnitListData(WorkUnitListDataBase):
    """All WorkUnits."""

    def get_workunit_list_qs(self):
        return WorkUnit.objects.all()


class WorkUnitRequirementsData(WorkUnitListDataBase):
    """WorkUnits that the specified WorkUnit requires."""

    def get_workunit_list_qs(self):
        return self.get_work_unit().requirements.all()


class WorkUnitRequiredByData(WorkUnitListDataBase):
    """WorkUnits that require the specified WorkUnit."""

    def get_workunit_list_qs(self):
        return self.get_work_unit().required_by.all()


class WorkUnitCreatedData(WorkUnitListDataBase):
    """WorkUnits created by the specified WorkUnit."""

    def get_workunit_list_qs(self):
        return self.get_work_unit().created.all()


class WorkUnitCreatedByData(WorkUnitListDataBase):
    """The WorkUnit that created the specified WorkUnit."""

    def get_workunit_list_qs(self):
        wu = self.get_work_unit()
        return WorkUnit.objects.filter(pk=wu.creator_id)


class WorkUnitActiveData(WorkUnitListDataBase):
    """WorkUnits currently under lease."""

    def get_workunit_list_qs(self):
        return WorkUnit.objects.exclude(lease_holder="").filter(Q(leased_until__gte=utcnow()))


class WorkUnitDescendantTreeData(WorkflowAjaxView):
    def get_ajax_data(self):
        def mk_tree_node(wu, children):
            # `children` can be a boolean (if True, this node has children) or a list of the actual children.
            return {
                "id": wu.pk,
                "text": str(wu),
                "icon": False,
                "children": children,
                "state": {"opened": children and children is not True},
                "status_url": self._reverse("workunit_status", {"pk": wu.pk}),
            }

        pk = int(self.request.GET.get("pk"))
        workunit = WorkUnit.objects.get(pk=pk)
        child_workunits = list(WorkUnit.objects.filter(creator=workunit).select_related("payload_ctype"))
        if child_workunits:
            child_pks = [c.pk for c in child_workunits]
            children_with_children = set(
                WorkUnit.objects.filter(creator_id__in=child_pks).values_list("creator_id", flat=True).distinct()
            )
            child_tree_nodes = [mk_tree_node(c, c.pk in children_with_children) for c in child_workunits]
        else:
            child_tree_nodes = False
        return mk_tree_node(workunit, child_tree_nodes)


class WorkUnitAncestors(WorkflowDetailsView):
    model = WorkUnit
    template_name = "workflow/workunit_ancestors.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workunit = kwargs["object"]
        ancestors = []
        self._recursive_get_ancestors(ancestors, self.object)
        ancestors.reverse()
        context.update(
            {"ancestors": ancestors, "workunit_status_url": self._reverse("workunit_status", {"pk": workunit.pk})}
        )
        return context

    def _recursive_get_ancestors(self, ret, wu):
        if wu is None:
            return
        # Attaching an attribute to the workunit so the template doesn't have to resolve the link
        wu.status_link = self._reverse("workunit_status", wu)
        ret.append(wu)
        self._recursive_get_ancestors(ret, wu.creator)


class WorkUnitDescendants(WorkflowDetailsView):
    model = WorkUnit
    template_name = "workflow/workunit_descendants.html"

    def get_links(self, **kwargs) -> LinksDict:
        workunit = kwargs["object"]
        links = super().get_links(**kwargs)
        links.update(
            {
                "workunit_created_by_tree_data": self._reverse("workunit_created_by_tree_data"),
                "workunit_status_url": self._reverse("workunit_status", {"pk": workunit.pk}),
            }
        )
        return links


class MarkAsFeasible(WorkflowView, View):
    def post(self, request, *args, **kwargs):
        pks = {int(pk) for pk in request.POST.getlist("pks[]")}
        work_units = WorkUnit.mark_as_feasible_for_ids(pks)
        new_states = {work_unit.pk: work_unit.state_str() for work_unit in work_units}
        return JsonResponse({"new_states": new_states})


# WorkException views.


class WorkExceptionLogView(WorkflowTemplateView):
    template_name = "workflow/workexceptionlog_list.html"

    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        links.update(
            {
                "workexceptionlog_data": self._reverse("workexceptionlog_data"),
                "mark_as_feasible": self._reverse("mark_as_feasible"),
                "workunit_list_data": self._reverse("workunit_list_data"),
            }
        )
        return links


class WorkExceptionLogDetail(WorkflowDetailsView):
    model = WorkExceptionLog

    def get_links(self, **kwargs) -> LinksDict:
        links = super().get_links(**kwargs)
        workunit = kwargs["object"].work_unit
        links.update({"workunit_status_url": self._reverse("workunit_status", {"pk": workunit.pk})})
        return links


class WorkExceptionLogDataBase(WorkflowAjaxView):
    def get_workexception_list_base_qs(self):
        raise NotImplementedError()

    def get_work_unit_pk(self):
        workunit_id_str = self.request.GET.get("work_unit_pk")
        return None if workunit_id_str is None else int(workunit_id_str)

    def get_ajax_data(self):
        search = self.request.GET.get("search")
        offset = int(self.request.GET.get("offset", 0))
        limit = int(self.request.GET.get("limit", 25))
        sort = self.request.GET.get("sort")
        order = self.request.GET.get("order")
        if sort and order == "desc":
            sort = f"-{sort}"

        workexceptions_qs = self.get_workexception_list_base_qs().select_related(
            "work_unit", "work_unit__payload_ctype"
        )
        if search:
            workexceptions_qs = workexceptions_qs.filter(search_vector=search)
        workexceptions_qs = workexceptions_qs.order_by(sort or "-timestamp")

        workexceptions, total = get_rows_and_total_size(workexceptions_qs, offset, limit)

        workexception_dicts = [
            {
                "id": we.id,
                "timestamp": we.timestamp,
                "category": we.category,
                "work_unit": f"{we.work_unit.payload_ctype.model} {we.work_unit.description}",
                "work_unit_pk": we.work_unit.pk,
                "work_unit__state_str": we.work_unit.state_str(),
                "message": we.message,
                "details_link": self._reverse("workexceptionlog_detail", we),
            }
            for we in workexceptions
        ]
        ret = {"total": total, "rows": workexception_dicts}
        return ret


class WorkExceptionLogData(WorkExceptionLogDataBase):
    def get_workexception_list_base_qs(self):
        return WorkExceptionLog.objects.all()


class WorkExceptionsForWorkUnitData(WorkExceptionLogDataBase):
    def get_workexception_list_base_qs(self):
        return WorkExceptionLog.objects.filter(work_unit_id=self.get_work_unit_pk())


def get_workflow_admin_urls(db_name: str):
    admin_urls = [
        # WorkUnit-related views.
        path("summary/", WorkflowSummary.as_view(db_name=db_name), name="summary"),
        path("workunit/stats/", WorkUnitStatsData.as_view(db_name=db_name), name="workunit_stats"),
        path(
            "workunit/stats/recompute/",
            WorkUnitStatsRecompute.as_view(db_name=db_name),
            name="workunit_stats_recompute",
        ),
        path("workunit/status/<int:pk>/", WorkUnitStatus.as_view(db_name=db_name), name="workunit_status"),
        path("workunit/ancestors/<int:pk>/", WorkUnitAncestors.as_view(db_name=db_name), name="workunit_ancestors"),
        path(
            "workunit/descendants/<int:pk>/", WorkUnitDescendants.as_view(db_name=db_name), name="workunit_descendants"
        ),
        path(
            "workunit/requirements/",
            WorkUnitRequirementsData.as_view(db_name=db_name),
            name="workunit_requirements_data",
        ),
        path(
            "workunit/required_by/", WorkUnitRequiredByData.as_view(db_name=db_name), name="workunit_required_by_data"
        ),
        path("workunit/created/", WorkUnitCreatedData.as_view(db_name=db_name), name="workunit_created_data"),
        path("workunit/created_by/", WorkUnitCreatedByData.as_view(db_name=db_name), name="workunit_created_by_data"),
        path(
            "workunit/created_by_tree/",
            WorkUnitDescendantTreeData.as_view(db_name=db_name),
            name="workunit_created_by_tree_data",
        ),
        path("workunits/active/", WorkUnitActiveData.as_view(db_name=db_name), name="workunit_active_data"),
        path("workunits/list/", WorkUnitList.as_view(db_name=db_name), name="workunit_list"),
        path("workunits/list/data/", WorkUnitListData.as_view(db_name=db_name), name="workunit_list_data"),
        path("workunit/mark_as_feasible/", MarkAsFeasible.as_view(db_name=db_name), name="mark_as_feasible"),
        # WorkException-related views.
        path(
            "workexception/<int:pk>/", WorkExceptionLogDetail.as_view(db_name=db_name), name="workexceptionlog_detail"
        ),
        path("workexceptions/", WorkExceptionLogView.as_view(db_name=db_name), name="workexceptionlog_list"),
        path("workexceptions/data/", WorkExceptionLogData.as_view(db_name=db_name), name="workexceptionlog_data"),
        path(
            "workexceptions/for/",
            WorkExceptionsForWorkUnitData.as_view(db_name=db_name),
            name="workexceptionsforworkunit_data",
        ),
    ]
    return admin_urls

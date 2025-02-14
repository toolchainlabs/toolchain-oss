# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.webresource.models import WebResource
from toolchain.workflow.admin_views import WorkflowDetailsView


class WebResourceDetail(WorkflowDetailsView):
    """Show details of a single WebResource."""

    model = WebResource

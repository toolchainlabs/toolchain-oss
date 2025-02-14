# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.template.response import TemplateResponse


def render_template_response(*, request, status, template, context):
    return TemplateResponse(request=request, status=status, template=template, context=context)

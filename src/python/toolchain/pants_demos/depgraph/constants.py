# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.resources.template_loaders import get_jinja2_template_config

TEMPLATES_CONFIG = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    }
] + get_jinja2_template_config(add_csp_extension=True)

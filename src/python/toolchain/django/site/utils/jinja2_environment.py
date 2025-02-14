# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import humanize
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from jinja2 import Environment

from toolchain.base.datetime_tools import datetime_fmt_std, seconds_from_now
from toolchain.base.toolchain_error import ToolchainAssertion


def environment(**options):
    if options.pop("autoescape", None) is False:
        # https://bandit.readthedocs.io/en/latest/plugins/b701_jinja2_autoescape_false.html
        raise ToolchainAssertion("autoescape is disabled. This is dangerous.")
    extensions = options.pop("extensions", [])
    env = Environment(extensions=extensions, autoescape=True, **options)
    env.globals.update(
        {
            "static": staticfiles_storage.url,
            "url": reverse,
            "hasattr": hasattr,
        }
    )
    env.filters.update(
        {
            "datetime_fmt_std": datetime_fmt_std,
            "seconds_from_now": seconds_from_now,
            "humanize_time": humanize.naturaldelta,
        }
    )
    return env

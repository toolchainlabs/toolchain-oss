# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.notifications.email.topic import Topic


@Topic.register_topic
class DummyEmailTopic(Topic):
    @classmethod
    def validate(cls, context_data):
        pass

    @classmethod
    def max_frequency(cls) -> datetime.timedelta:
        return datetime.timedelta(days=3)

    @classmethod
    def template_name(cls) -> str:
        return "dummy_email.html"

    def get_subject(cls) -> str:
        return "Integration Test Email #1"

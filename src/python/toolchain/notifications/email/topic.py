# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import datetime
from typing import Any

from toolchain.django.site.models import ToolchainUser

ContextData = dict[str, Any]


class Topic(abc.ABC):
    """Base class for notification topics. Each topic provides validation logic and supports the logic needed to do
    deduplication. It also support the rendering logic by providing the email subject and the template used to render
    the email.

    This class is responsible for maintaining a registry of email topics and provide an API to access them.
    """

    _topics: dict[str, type[Topic]] = {}

    def __init__(self, user: ToolchainUser, context_data: ContextData) -> None:
        self.user = user
        self.context_data = context_data

    @classmethod
    def register_topic(cls, subclass):
        """Registers the topic for use in the `topic` field of `EmailMessage`.

        When an `EmailMessage` is pulled from the database for sending, this class will be fetched from `Topic.topics`.
        """
        cls.register(subclass)
        cls._topics[subclass.__name__] = subclass
        return subclass

    @classmethod
    def validate_topic(cls, topic_name: str, context_data: ContextData):
        topic = cls._topics[topic_name]
        topic.validate(context_data)

    @classmethod
    def get_topic(cls, type_name: str, user: ToolchainUser, context: ContextData) -> Topic:
        topic_type = cls._topics[type_name]
        return topic_type(user, context)

    @classmethod
    @abc.abstractmethod
    def validate(cls, context_data: ContextData) -> None:
        """Verifies that the message contains data necessary to correctly render the email.

        Throw an exception if validation fails.
        """

    @classmethod
    @abc.abstractmethod
    def max_frequency(cls) -> datetime.timedelta:
        """Returns a timedelta representing the the shortest allowable gap between two messages of this topic with the
        same `message_key` value."""

    @classmethod
    @abc.abstractmethod
    def template_name(cls) -> str:
        """Returns the name of the template used to render the email."""

    @abc.abstractmethod
    def get_subject(self) -> str:
        """Returns the name of the template used to render the email."""

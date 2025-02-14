# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from collections.abc import Iterator
from contextlib import suppress
from functools import cached_property

import jinja2
import pkg_resources
from django.apps import apps
from django.template import Origin, TemplateDoesNotExist
from django.template.loaders.base import Loader
from django.template.utils import get_app_template_dirs

_logger = logging.getLogger(__name__)


# Template loaders, for the Django and Jinja2 template engines, that load templates as resources
# from Python packages.  This allows us to run Django apps from PEX files.
# Note that these loaders also support loading from the filesystem, when running direct from local sources
# during development.  So we don't need to handle that case separately in settings.
class PackageOrigin(Origin):
    """A Django template origin representing a location in a package."""

    def __init__(self, module, relpath, name, template_name=None, loader=None):
        super().__init__(name, template_name, loader)
        self.module = module
        self.relpath = relpath


class DjangoPackageLoader(Loader):
    """A Django template loader that loads from package resources."""

    def get_contents(self, origin) -> str:
        try:
            contents = pkg_resources.resource_string(origin.module, origin.relpath)
        except OSError:
            raise TemplateDoesNotExist(origin)
        return contents.decode() if isinstance(contents, bytes) else contents

    def get_template_sources(self, template_name: str) -> Iterator[PackageOrigin]:
        relpath = f"templates/{template_name}"
        for app_config in apps.get_app_configs():
            yield PackageOrigin(
                module=app_config.module.__name__,
                relpath=relpath,
                name=f"{app_config.module.__name__}:{relpath}",
                template_name=template_name,
                loader=self,
            )


# Loaders for the Jinja2 engine.


class DelegatingJinja2Loader(jinja2.BaseLoader):
    """A Jinja2 template loader that delegates to some other, lazily-constructed loader.

    Unlike Django template loaders, which are provided by name, the Jinja2 loader must actually be constructed eagerly
    in settings.py.  However our actual loading logic cannot be constructed eagerly there, because it relies on the app
    registry.  So we delegate via this loader, which creates the underlying loader lazily.
    """

    def __init__(self, delegate_factory):
        super().__init__()
        self._delegate_factory = delegate_factory

    @cached_property
    def _delegate(self):
        return self._delegate_factory()

    def get_source(self, environment, template):
        return self._delegate.get_source(environment, template)

    def load(self, environment, name, globals=None):
        return self._delegate.load(environment, name, globals)


def _app_directory_loader_factory():
    # This is exactly the loader that the Django Jinja2 integration lazily creates if you don't specify
    # one explicitly.  However since we want to chain this with another loader, we have to implement
    # the laziness ourselves.
    return jinja2.FileSystemLoader(get_app_template_dirs("jinja2"))


class Jinja2AppDirectoryLoader(DelegatingJinja2Loader):
    """A Jinja2 template loader that loads templates from multiple app directories on the filesystem."""

    def __init__(self):
        super().__init__(_app_directory_loader_factory)


def _app_package_loader_factory():
    # Jinja2 already has a PackageLoader class, but it only works on a single package.
    # The ChoiceLoader tries each PackageLoader in turn until it finds the template (and then caches it).
    loaders = []
    for app_config in apps.get_app_configs():
        name = app_config.module.__name__
        with suppress(ValueError):
            # PackageLoader raises a value error if the package doesn't have a jinja2 module.
            # https://github.com/pallets/jinja/blob/f20a9c9ccbbfae312581ca9e740dcbecc218fad0/src/jinja2/loaders.py#L311
            loaders.append(jinja2.PackageLoader(package_name=name, package_path="jinja2"))
    return jinja2.ChoiceLoader(loaders)


class Jinja2AppPackageLoader(DelegatingJinja2Loader):
    """A loader for the Jinja2 template engine that loads templates from package resources in multiple apps."""

    def __init__(self):
        super().__init__(_app_package_loader_factory)


def get_jinja2_template_config(add_csp_extension: bool = False):
    template_config = [
        {
            "BACKEND": "django.template.backends.jinja2.Jinja2",
            "OPTIONS": {
                "environment": "toolchain.django.site.utils.jinja2_environment.environment",
                "extensions": ["csp.extensions.NoncedScript"] if add_csp_extension else [],
                "loader": jinja2.ChoiceLoader(
                    # NB: The Jinja2AppPackageLoader will load from the filesystem when running directly from
                    # sources during development, but it won't reload templates on file changes, which is a crucial
                    # feature when developing. so we try an Jinja2AppDirectoryLoader first.
                    [Jinja2AppDirectoryLoader(), Jinja2AppPackageLoader()]
                ),
            },
        }
    ]
    return template_config

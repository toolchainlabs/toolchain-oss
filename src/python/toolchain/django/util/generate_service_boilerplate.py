#!/usr/bin/env ./python
# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import os
from argparse import ArgumentParser, Namespace

import jinja2

from toolchain.base.datetime_tools import utcnow
from toolchain.base.fileutil import safe_mkdir
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.config.services import get_gunicorn_service

logger = logging.getLogger(__name__)


# Strip this suffix off any filenames that have it.
# We can't use '.template' because 'BUILD.template' would look like a real BUILD file.
_strip_suffix = "_template"


class ServiceBoilerplateGenerator(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        service_name = cmd_args.service_name
        service = get_gunicorn_service(service_name)
        self._template_args = {
            "service_name": service_name,
            "service_name_dashes": service.name,
            "service_pkg": service.package,
            "service_shortname": service_name.rsplit("/", 1)[-1],
            "dev_port": service.dev_port,  # User must have already updated config/services.json.
            "copyright_year": utcnow().date().year,
        }

    def run(self) -> int:
        self.generate(os.path.join("src", "python", "toolchain", "service"))
        self.generate(os.path.join("prod", "helm"), output_dir_suffix=self._template_args["service_name_dashes"])
        return 0

    def generate(self, gendir, output_dir_suffix=""):
        env = jinja2.Environment(autoescape=True, loader=jinja2.FileSystemLoader(os.path.join(gendir, "_jinja2")))
        output_dir = os.path.join(gendir, self._template_args["service_name"].replace("/", os.sep))
        if output_dir_suffix:
            output_dir = os.path.join(output_dir, output_dir_suffix)
        for template in env.list_templates():
            output_path = os.path.join(output_dir, os.sep.join(template.split("/")))
            if output_path.endswith(_strip_suffix):
                output_path = output_path[0 : -len(_strip_suffix)]
            safe_mkdir(os.path.dirname(output_path))
            logger.info(f"Creating {output_path}")
            env.get_template(template).stream(**self._template_args).dump(output_path, encoding="utf8")

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--service-name", metavar="my/service/name", required=True, help="The name of the service.")


if __name__ == "__main__":
    ServiceBoilerplateGenerator.start()

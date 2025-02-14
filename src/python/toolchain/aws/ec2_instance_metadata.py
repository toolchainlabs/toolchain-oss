# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from functools import cached_property

import requests


class EC2InstanceMetadata:
    _host = "169.254.169.254"
    _port = 80

    @cached_property
    def instance_id(self):
        return self._fetch_instance_metadata_text("/instance-id")

    @cached_property
    def local_hostname(self):
        return self._fetch_instance_metadata_text("/local-hostname")

    @cached_property
    def local_ipv4(self):
        return self._fetch_instance_metadata_text("/local-ipv4")

    @cached_property
    def availability_zone(self):
        return self._fetch_instance_metadata_text("/placement/availability-zone")

    @property
    def region(self):
        return self.availability_zone[:-1]

    def security_credentials(self, role):
        return self._fetch_instance_metadata_json(f"/iam/security-credentials/{role}")

    def _fetch_instance_metadata_text(self, subpath):
        return self._fetch_metadata_response(f"/latest/meta-data{subpath}").text

    def _fetch_instance_metadata_json(self, subpath):
        return self._fetch_metadata_response(f"/latest/meta-data{subpath}").json()

    def _fetch_metadata_response(self, path):
        url = f"http://{self._host}:{self._port}{path}"
        res = requests.get(url)
        res.raise_for_status()
        return res

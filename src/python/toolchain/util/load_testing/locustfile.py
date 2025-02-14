# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from locust import HttpUser, between, task


class InfoSite(HttpUser):
    wait_time = between(5, 15)

    @task
    def index(self):
        self.client.get("/")
        self.client.get("/static/infosite/js/main_v2.js")

    @task
    def about(self):
        self.client.get("/about")

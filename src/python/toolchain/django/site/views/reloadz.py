# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import signal
from pathlib import Path
from typing import Optional

from django.http import HttpResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name="dispatch")
class Reloadz(View):
    view_type = "checks"
    _PID_FILE = Path("/var/run/gunicorn/master.pid")  # see gunicorn_conf

    def _get_pid(self) -> Optional[int]:
        if not self._PID_FILE.exists():
            return None
        return int(self._PID_FILE.read_text("utf-8"))

    def get(self, _):
        pid = self._get_pid()
        return HttpResponse(str(pid or "NA"))

    def post(self, _):
        pid = self._get_pid()
        if not pid:
            return HttpResponseForbidden()
        os.kill(pid, signal.SIGTERM)
        return HttpResponse(str(pid))

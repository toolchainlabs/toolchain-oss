# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import time
from contextlib import contextmanager


class _Timer:
    def __init__(self):
        self._start = time.time()
        self._end = None

    def stop(self):
        self._end = time.time()

    def secs(self):
        return self._end - self._start


@contextmanager
def stopwatch():
    """A simple timer context.

    Use like this:

    with stopwatch() as sw:
      ... code to be timed ...

    print('Code took {:.3} seconds'.format(sw.secs()))
    """
    timer = _Timer()
    yield timer
    timer.stop()

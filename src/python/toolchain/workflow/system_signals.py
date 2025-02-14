# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import signal

_logger = logging.getLogger(__name__)


class SignalWrapper:
    SIGNALS = [signal.Signals.SIGTERM, signal.Signals.SIGQUIT]

    def __init__(self) -> None:
        self._should_quit = False
        self._register()

    def _register(self) -> None:
        for sig in self.SIGNALS:
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, sig_id: int, frame) -> None:
        sig_obj = signal.Signals(sig_id)
        _logger.info(f"Signal: {sig_obj} {frame=}")
        self._should_quit = True

    @property
    def should_quit(self) -> bool:
        return self._should_quit

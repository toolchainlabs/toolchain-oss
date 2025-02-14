# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

# An adaptor for logging that allows passing string templates with curly braces instead of `%s`.
# EG:
# `logger.info('hello {}', 'world')` in place of `logger.info('hello %s, 'world')`
# Passing arguments in place of preformatted strings is useful for perf reasons.

# To use the adaptor, use
# `logger = StyleAdapter(logging.getLogger(__name__))` where you would otherwise have used
# `logger = logging.getLogger(__name__)`


class Message:
    def __init__(self, fmt, args):
        self.fmt = fmt
        self.args = args

    def __str__(self):
        return self.fmt.format(*self.args)


class StyleAdapter(logging.LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, Message(msg, args), (), **kwargs)

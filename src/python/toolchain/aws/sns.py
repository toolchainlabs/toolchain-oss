# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.aws.aws_api import AWSService


class SNS(AWSService):
    service = "sns"

    def publish(self, topic_arn, msg):
        return self.client.publish(TopicArn=topic_arn, Message=msg)

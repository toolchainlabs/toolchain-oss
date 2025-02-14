# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

from toolchain.aws.sns import SNS
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.webresource.models import WebResource

act_on_web_resources_topic_arn = "arn:aws:sns:us-east-1:283194185447:act_on_web_resources"


def trigger_shards(shards=None):
    """Trigger action on the given shards of web resources of the given class.

    :param shards: A list of shards from the range (0-4095) to act on. If unspecified, will act on all shards.
    """
    shards = shards or range(0, 4096)
    sns = SNS()
    for shard in shards:
        msg = json.dumps({"shard": shard})
        sns.publish(act_on_web_resources_topic_arn, msg)


def action_func_wrapper(web_resource):
    # Act on web_resource here.
    pass


def handler(event, context):
    import django

    django.setup()

    transaction = TransactionBroker("webresource")

    for record in event["Records"]:
        msg = json.loads(record["Sns"]["Message"])
        shard = msg["shard"]

        try:
            WebResource.act_on_shard(shard, action_func_wrapper)
        except django.db.Error:
            # Some errors are caused by connection closes, so retry once in that case.
            transaction.connection.close()
            WebResource.act_on_shard(shard, action_func_wrapper)

# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import re
from dataclasses import dataclass

from toolchain.aws.aws_api import AWSService


@dataclass(frozen=True)
class RedisCluster:
    clustrer_id: str
    address: str
    port: int


class ElastiCache(AWSService):
    service = "elasticache"

    def get_redis_clusters(self, cluster_id_regex: re.Pattern) -> tuple[RedisCluster, ...]:
        cache_clusters = self.client.describe_cache_clusters(ShowCacheNodeInfo=True, MaxRecords=100)["CacheClusters"]
        if len(cache_clusters) >= 100:
            raise NotImplementedError("Pagination not implemented on describe_cache_clusters()")
        redis_clusters = []
        for cluster in cache_clusters:
            if cluster["Engine"] != "redis":
                continue
            cluster_id = cluster["CacheClusterId"]
            if not cluster_id_regex.match(cluster_id):
                continue
            nodes = cluster["CacheNodes"]
            if len(nodes) != 1:
                raise NotImplementedError(f"Unexpected number of cache nodes for {cluster_id}")
            ep = nodes[0]["Endpoint"]
            redis_clusters.append(RedisCluster(clustrer_id=cluster_id, address=ep["Address"], port=ep["Port"]))

        return tuple(redis_clusters)

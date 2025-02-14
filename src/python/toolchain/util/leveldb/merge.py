# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import heapq

import plyvel


def merge_table_paths(input_table_paths, output_table_path):
    merge_tables([plyvel.DB(path) for path in input_table_paths], plyvel.DB(output_table_path, create_if_missing=True))


def merge_tables(input_tables, output_table):
    batch_size = 10000
    input_iters = [input_table.iterator(fill_cache=False) for input_table in input_tables]
    i = 0
    batch = output_table.write_batch(sync=True)
    for k, v in heapq.merge(*input_iters):
        batch.put(k, v)
        i += 1
        if i == batch_size:
            batch.write()
            i = 0
            batch = output_table.write_batch(sync=True)
    batch.write()

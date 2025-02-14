# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import re

from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.util.file.create import create_directory, create_file

logger = logging.getLogger(__name__)


class InvalidOrdinalError(ToolchainError):
    """Raised when the url doesn't match the expected pattern.

    This can happen due to temporary files created as the file is being copied into a folder
    """


# For a leveldb at <base_dir_url>/leveldbs/01234/, the input list file is at <base_dir_url>/input_lists/01234
# These methods help navigate between the two.

# Utilities to find a leveldb and its corresponding input list file (a file containing the list of
# input files that went into computing the leveldb).


def ordinal_from_leveldb(leveldb_url: str) -> int:
    mo = re.match(r"^.*/leveldbs/(?P<ordinal>\d{5})/$", leveldb_url)
    if mo is None:
        raise ToolchainAssertion(f"Not a valid leveldb URL: {leveldb_url}")
    return int(mo.group("ordinal"))


def ordinal_from_input_list(input_list_url: str) -> int:
    mo = re.match(r"^.*/input_lists/(?P<ordinal>\d{5})$", input_list_url)
    if mo is None:
        raise InvalidOrdinalError(f"Not a valid input list URL: {input_list_url}")
    return int(mo.group("ordinal"))


def leveldb_for_ordinal(base_dir_url: str, ordinal: int) -> str:
    return f"{base_dir_url}leveldbs/{ordinal:05}/"


def input_list_base(base_dir_url: str) -> str:
    return f"{base_dir_url}input_lists/"


def input_list_for_ordinal(base_dir_url: str, ordinal: int) -> str:
    return f"{input_list_base(base_dir_url)}{ordinal:05}"


def base_dir_url_from_leveldb(leveldb_url: str) -> str:
    return leveldb_url[0 : -len("leveldbs/00000/")]


def base_dir_url_from_input_list(input_list_url: str) -> str:
    return input_list_url[0 : -len("input_lists/00000")]


def input_list_for_leveldb(leveldb_url: str) -> str:
    base_url = base_dir_url_from_leveldb(leveldb_url)
    ordinal = ordinal_from_leveldb(leveldb_url)
    return input_list_for_ordinal(base_url, ordinal)


def leveldb_for_input_list(input_list_url: str) -> str:
    base_url = base_dir_url_from_input_list(input_list_url)
    ordinal = ordinal_from_input_list(input_list_url)
    return leveldb_for_ordinal(base_url, ordinal)


def copy_leveldb_and_input_list(src_basedir_url: str, tgt_basedir_url: str, ordinal: int) -> None:
    src_leveldb = leveldb_for_ordinal(src_basedir_url, ordinal)
    tgt_leveldb = leveldb_for_ordinal(tgt_basedir_url, ordinal)
    logger.info(f"Copying {src_leveldb} to {tgt_leveldb}")
    create_directory(src_leveldb).copy_to(create_directory(tgt_leveldb))

    src_input_list = input_list_for_ordinal(src_basedir_url, ordinal)
    tgt_input_list = input_list_for_ordinal(tgt_basedir_url, ordinal)
    logger.info(f"Copying {src_input_list} to {tgt_input_list}")
    create_file(src_input_list).copy_to(create_file(tgt_input_list))


def delete_leveldb_and_input_list(basedir_url, ordinal):
    logger.info(f"Deleting leveldb at {basedir_url} {ordinal:05}")
    create_file(input_list_for_ordinal(basedir_url, ordinal)).delete()
    create_directory(leveldb_for_ordinal(basedir_url, ordinal)).delete()

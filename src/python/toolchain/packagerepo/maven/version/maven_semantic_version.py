# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re
from functools import total_ordering

# From https://maven.apache.org/pom.html#Version_Order_Specification:
# Non-numeric tokens have the alphabetical order, except for the following tokens which come first in this order:
#     "alpha" < "beta" < "milestone" < "rc" = "cr" < "snapshot" < "" = "final" = "ga" < "sp"
SPECIAL_CASE_STRINGS = {
    "alpha": 0,
    "beta": 1,
    "milestone": 2,
    "rc": 3,
    "cr": 3,
    "snapshot": 4,
    "": 5,
    "final": 5,
    "ga": 5,
    "sp": 6,
}

NULL_VALUES = ["0", "", "final", "ga"]

SEPARATORS = ["-", "."]


class MavenSemverPart:
    """Represents a part of a mavenSemver consisting of a prefix and a token.

    The prefixed token order is:

    if the prefix is the same, then compare the token:   Numeric tokens have the natural order.   Non-numeric
    ("qualifiers") tokens have the alphabetical order, except for those in SEPCIAL_CASE_STRINGS     which come first.

    else ".qualifier" < "-qualifier" < "-number" < ".number"
    """

    def __init__(self, prefix, token):
        self.prefix = prefix
        self.token = token

    def __repr__(self):
        return f"{self.prefix}{self.token}"

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if self.prefix != other.prefix:
            return False
        if self.token.isdigit() and other.token.isdigit():
            return int(self.token) == int(other.token)
        if is_alpha(self.token) and is_alpha(other.token):
            if self.token in SPECIAL_CASE_STRINGS and other.token in SPECIAL_CASE_STRINGS:
                # Some special case strings have equal values. '' == 'final' and 'rc' == 'cr'
                return SPECIAL_CASE_STRINGS[self.token] == SPECIAL_CASE_STRINGS[other.token]
            return self.token == other.token
        return False

    def __lt__(self, other):
        # non-numeric tokens are always less than numeric tokens.
        if is_alpha(self.token) and other.token.isdigit():
            return True
        if self.token.isdigit() and is_alpha(other.token):
            return False

        prefixes_match = self.prefix == other.prefix
        if self.token.isdigit() and other.token.isdigit():
            return int(self.token) < int(other.token) if prefixes_match else self.prefix < other.prefix

        if is_alpha(self.token) and is_alpha(other.token):
            # Note: lexical sorting of '.' and '-' is reversed for non-numeric tokens.
            return self._alpha_less_than(other) if prefixes_match else other.prefix < self.prefix

        else:
            raise TypeError(f"Expected alphanumeric, Received: '{self.token}', '{other.token}'.")

    def _alpha_less_than(self, other):
        """Compare non-numeric parts.

        Non-numeric tokens have the alphabetical order, except for the following tokens which come first in this order:
        "alpha" < "beta" < "milestone" < "rc" = "cr" < "snapshot" < "" = "final" = "ga" < "sp"
        """
        if self.token == other.token:
            return False
        if self.token in SPECIAL_CASE_STRINGS:
            if other.token in SPECIAL_CASE_STRINGS:
                return SPECIAL_CASE_STRINGS[self.token] < SPECIAL_CASE_STRINGS[other.token]
            else:
                return True
        elif other.token in SPECIAL_CASE_STRINGS:
            return False
        else:
            return self.token < other.token


def version_string_from_parts(version_parts):
    return "".join([f"{part.prefix}{part.token}" for part in version_parts])


def canonicalize_version_string(version):
    canonical_parts = split_version_string_parts(version)
    return version_string_from_parts(canonical_parts)


def trim_trailing(parts):
    """Remove trailing null values and separators. This process is repeated at each remaining hypen from end to start.

    '1.0' --> '1', '1.0-foo' --> '1-foo'
    """
    while parts[-1] in NULL_VALUES or parts[-1] in SEPARATORS:
        parts = parts[:-1]

    for i, part in reversed(list(enumerate(parts))):
        if part == "-":
            return trim_trailing(parts[:i]) + parts[i:]
    return parts


def split_version_string_parts(version):
    """Canonicalize version string and return a tuple of MavenSemverParts."""
    # When preceded by a non-alpha character and followed directly by a number, 'a', 'b' and 'm' are equivalent to
    # 'alpha', 'beta' and 'milestone' respectively.
    # 'a1' --> alpha1
    version = re.sub(
        r"(?P<preceding>(?:\A|[^a-zA-Z]))a(?P<succeeding>\d)", r"\g<preceding>alpha\g<succeeding>", version
    )
    # 'b1' --> 'beta1'
    version = re.sub(r"(?P<preceding>(?:\A|[^a-zA-Z]))b(?P<succeeding>\d)", r"\g<preceding>beta\g<succeeding>", version)
    # 'm1' --> 'milestone1'
    version = re.sub(
        r"(?P<preceding>(?:\A|[^a-zA-Z]))m(?P<succeeding>\d)", r"\g<preceding>milestone\g<succeeding>", version
    )

    # Boundaries between digits and alpha characters are equivalent to '-'.
    # '0beta4' --> '0-beta-4'
    version = re.sub(r"(?<=\d)(?=[a-zA-Z])|(?<=[a-zA-Z])(?=\d)", "-", version)

    # Empty tokens are equivalent to 0
    # '1-.1' --> '1-0.1'
    version = re.sub(r"(?<=\W)(?=\W)", "0", version)

    # Split version string into list.
    # '1.beta-1' --> ['1', '.', 'beta', '-', '1']
    parts = re.split(r"(\W+)", version)

    # Remove trailing null values or seperators.
    # '1.0' --> '1', '1.0-foo' --> '1-foo'
    parts = trim_trailing(parts)

    # Pair parts into (prefix, token) tuples. The leading '' added here simplifies the (prefix, token) arrangement.
    # ['1', '.', 'beta', '-', '1'] --> [('','1'), ('.', 'beta'), ('-', '1')]
    part_pairs = zip(*[iter([""] + parts)] * 2)
    return tuple(MavenSemverPart(prefix=prefix, token=token) for prefix, token in part_pairs)


def is_alpha(part):
    """This needs to match empty strings, special characters, and alpha characters."""
    return not part.isdigit()


def _pad_shorter(shorter, longer):
    def pad_value_for_part(part):
        if part.prefix == ".":
            return MavenSemverPart(".", "0")
        return MavenSemverPart("-", "")

    start_index = len(shorter)
    padding = tuple(pad_value_for_part(part) for part in longer[start_index:])
    return shorter + padding


def pad_shorter_version(first_version_parts, second_version_parts):
    """Pad the shorter version with enough "null" values with matching prefix to have the same length as the longer one.
    Padded "null" values depend on the prefix of the other version: 0 for '.', "" for '-'.

    Padding the shorter of two versions is necessary due to the existence of special case strings:

    '1.alpha' < '1' < '1.sp'
    """
    length_first = len(first_version_parts)
    length_second = len(second_version_parts)
    if length_first < length_second:
        first_version_parts = _pad_shorter(shorter=first_version_parts, longer=second_version_parts)
    elif length_first > length_second:
        second_version_parts = _pad_shorter(shorter=second_version_parts, longer=first_version_parts)
    return first_version_parts, second_version_parts


@total_ordering
class MavenSemver:
    """Represents a Maven Artifact Version - eg: '1.0.2-beta' and provides sort functionality.

    Note: Maven does not enforce semantic versioning as it is generally defined, but it does have its own
    homegrown semantics of what makes a version and how those versions should be sorted.
    """

    def __init__(self, version):
        self.version = version
        self.version_parts = split_version_string_parts(version)

    def __repr__(self):
        return self.version

    def __hash__(self):
        return hash(self.version)

    def __eq__(self, other):
        if not isinstance(other, MavenSemver):
            return False
        parts = zip(*pad_shorter_version(self.version_parts, other.version_parts))
        return all(self_part == other_part for self_part, other_part in parts)

    def __lt__(self, other):
        for self_part, other_part in zip(*pad_shorter_version(self.version_parts, other.version_parts)):
            if self_part == other_part:
                continue
            return self_part < other_part
        return False

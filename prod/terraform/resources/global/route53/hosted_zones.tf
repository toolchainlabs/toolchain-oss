# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_route53_zone" "snowchain_io" {
  name = "snowchain.io"
}

resource "aws_route53_zone" "toolchainlabs_com" {
  name = "toolchainlabs.com"
}

resource "aws_route53_zone" "toolchain_com" {
  name = "toolchain.com"
}

resource "aws_route53_zone" "toolchain_build" {
  name = "toolchain.build"
}

resource "aws_route53_zone" "toolchain_private" {
  name = "toolchain.private"
  vpc {
    vpc_id = data.aws_vpc.remoting_prod.id
  }
  vpc {
    vpc_id = data.aws_vpc.main.id
  }
}

resource "aws_route53_zone" "graphmyrepo_com" {
  name = "graphmyrepo.com"
}

resource "aws_route53_zone" "graphmycode_com" {
  name = "graphmycode.com"
}

# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import boto3
from moto.acm.models import CertBundle
from moto.core import DEFAULT_ACCOUNT_ID


def create_fake_security_group(region, group_name):
    ec2 = boto3.client("ec2", region_name=region)
    vpc_id = ec2.create_vpc(CidrBlock="10.0.0.0/24")["Vpc"]["VpcId"]
    sg_id = ec2.create_security_group(Description="Bizarro Jerry", GroupName=group_name, VpcId=vpc_id)["GroupId"]
    return sg_id


def create_fake_elb(region: str, cert_arn: str) -> dict:
    ec2 = boto3.client("ec2", region_name=region)
    vpc_id = ec2.create_vpc(CidrBlock="10.0.0.0/24")["Vpc"]["VpcId"]
    sg_id = create_fake_security_group(region, "superman")
    subnet_id = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.0.0/24")["Subnet"]["SubnetId"]
    elbv2 = boto3.client("elbv2", region_name=region)
    elb = elbv2.create_load_balancer(Name="gold-jerry", Subnets=[subnet_id], SecurityGroups=[sg_id])["LoadBalancers"][0]
    elb_arn = elb["LoadBalancerArn"]
    elbv2.create_listener(
        LoadBalancerArn=elb_arn,
        Port=9099,
        Protocol="HTTPS",
        DefaultActions=[],
        Certificates=[{"CertificateArn": cert_arn}],
    )
    elb = elbv2.describe_load_balancers(LoadBalancerArns=[elb_arn])["LoadBalancers"][0]
    return elb


def create_fake_cert(region: str, fqdn: str, import_cert: bool = True) -> str:
    client = boto3.client("acm", region_name=region)
    cert_arn = client.request_certificate(DomainName=fqdn, ValidationMethod="DNS")["CertificateArn"]
    cert_bundle = CertBundle.generate_cert(domain_name=fqdn, account_id=DEFAULT_ACCOUNT_ID, region=region)
    if import_cert:
        client.import_certificate(CertificateArn=cert_arn, Certificate=cert_bundle.cert, PrivateKey=cert_bundle.key)
    return cert_arn

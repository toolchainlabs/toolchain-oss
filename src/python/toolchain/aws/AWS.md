# AWS Primer

AWS (Amazon Web Services) consists of about a hundred services,
each with its own acronym and terminology.

This document provides a brief primer of relevant services.
It will omit many concepts, but will touch on the ones we most
frequently interact with directly, in practice.

## General concepts

A _region_ is a separate geographical area in which AWS maintains a datacenter.
For example, we use `us-west-2`, which is in Oregon, for storing general-purpose
state, and we deploy a crawler in `us-east-1`, which is in Virginia.

Each region has multiple, isolated locations known as _availability zones_.
Each availability zone is independent in terms of power, network etc., but
all AZs in the same region are connected by low-latency links.
Spreading services and data across multiple AZs provides redundancy and
resilience to failure, without having to think about the much harder problem
of replicating across regions.

It is, of course, possible for an entire region to fail, but Amazon considers it rare.

## IAM

IAM (Identity and Access Management) is a sophisticated
[authentication](https://docs.aws.amazon.com/IAM/latest/UserGuide/id.html) and
[authorization](https://docs.aws.amazon.com/IAM/latest/UserGuide/access.html) service,
used ubiquitously across AWS.

A _user_ is an identity with a username and password, providing control over access to AWS resources
by people or services.  A user can access the AWS management console, and use the AWS API or CLI.

A _group_ is a collection of users. It simplifies managing permissions for multiple users at once.

A _role_ is an identity, similar to a user, except it does not have any credentials associated with it.
An IAM user or an AWS service can assume a role to temporarily take on different permissions for a specific task.

A _policy_ is a set of rules controlling access to some resource.  Policies are attached to users,
groups and roles.

Resources are identified via _ARNs_ (Amazon Resource Names), see
[here](https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html#genref-arns)
for examples.

Usernames/passwords are used directly only when logging in to the management console.
Programmatic access to AWS resources, via API or CLI, uses _access keys_, generated
for a user. An access key is a pair of (access key ID, secret access key), and the secret
is only accessible at the time you create the access key.  If you lose the secret you have
to regenerate a new access key.

## EC2

EC2 (Elastic Compute Cloud) is a hosted computing environment, allowing users to rent
compute capacity in the cloud.  This is the fundamental AWS service, and is what most
people think of when they casually refer to "AWS".

A single virtual computer running on EC2 is called an _instance_.  This is the basic
unit of deployment. Users spin instances up and down as needed.

An _instance type_ comprises varying [combinations](https://aws.amazon.com/ec2/instance-types/)
of CPU, memory, storage, and networking capacity, and provides the flexibility to choose the
appropriate mix of resources for a given application.

An instance is booted from an _AMI_ (Amazon Machine Image) of your choice.  There are
many AMIs to choose from, each with a specific combination of OS and other software preinstalled.
If using Docker, the docker images running inside the EC2 instance encapsulate the OS and software requirements.
So that instance's AMI need only contain the software needed to run Docker containers.  
We use the Amazon ECS-Optimized AMI for this purpose.

## VPC

VPC (Virtual Private Cloud) provides a virtual networking environment. Users have complete control
over subnets, routing and network gateways.

A _security group_ is a virtual firewall attached to an EC2 instance.
Each security group has a set of rules controlling inbound traffic, and another set of rules
controlling outbound traffic.

VPC has too many concepts to list here. We recommend Amazon's
[documentation](https://aws.amazon.com/documentation/vpc/).

## S3

S3 (Simple Storage Service) is a distributed "filesystem" in the style of
[GFS](https://research.google.com/archive/gfs.html).
Files are referred to as _objects_.  Objects are organized into _buckets_.
Within a bucket, each object is identified by a _key_.

The bucket+key combo is sometimes written as `s3://bucket/key`.  For example, the
AWS CLI understands these URIs.

Objects are also addressable via standard HTTP URLs: `http://s3.amazonaws.com/bucket/key`.

As with GFS, directories are not a first-class entity in S3. However, keys with slashes in them are treated
hierarchically by some browsing tools, and by the CLI.  E.g., you can `aws ls s3://bucket/path/to/key`
and see all objects with that prefix, up to the next slash.

## EKS

EKS (EC2 Kubernetes Service) is a hosted Kubernetes control plane.

## ECR

The ECR (EC2 Container Registry) is a Docker image registry, similar to DockerHub, but managed by Amazon,
and utilizing IAM for authorization.

## RDS

RDS (Relational Database Service) is a managed database service, providing scaling, replication, backup and other
administration services for databases such as MySQL and PostgreSQL.

## Lambda

Lambda is a "serverless computing" service. It runs functions on your behalf without you having to provision servers.

## SES

SES (Simple Email Service) provides an SMTP interface for sending email.

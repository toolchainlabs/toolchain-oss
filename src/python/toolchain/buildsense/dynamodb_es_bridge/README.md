# DynamoDB to Elasticsearch Lambda function

## Description

This lambda function hooks into a DynamoDB Streams from the RunInfo table and updates the Elasticsearch index with data/documents coming from that stream.

We have two functions for the two buildsense environments.
The 'dev' function hooks up to DynamoDB stream from the Dev DynamoDB RunInfo table and updates the Dev Elasticsearch BuildSense index.
The 'prod' function does the same thing but for the production DynamoDB table and the production BuildSense Elasticsearch cluster/index.

## How to deploy

We have scripts that will build the pex file using pants, copy it to s3 and call AWS APIs to update function code:

```shell
./prod/python/toolchain_dev/deploy_es_lambda.sh
```

```shell
./prod/python/toolchain_prod/deploy_es_lambda.sh
```

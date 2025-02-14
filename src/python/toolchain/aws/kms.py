# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from base64 import b64decode, b64encode

from toolchain.aws.aws_api import AWSService


class KMS(AWSService):
    service = "kms"

    def list_keys(self):
        return self.client.list_keys()

    def encrypt(self, key_arn, plaintext):
        return b64encode(self.client.encrypt(KeyId=key_arn, Plaintext=plaintext)["CiphertextBlob"])

    def decrypt(self, encrypted):
        return self.client.decrypt(CiphertextBlob=b64decode(encrypted))["Plaintext"]

# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from rest_framework import serializers

from toolchain.packagerepo.pypi.models import Distribution, DistributionData, Project, Release


class ReleaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Release
        fields = ("version",)


class DistributionDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistributionData
        fields = ("modules",)


class DistributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distribution
        fields = ("filename", "dist_type", "release", "data")

    release = ReleaseSerializer()
    data = DistributionDataSerializer()


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ("name", "pypi_url", "releases")

    releases = ReleaseSerializer(many=True)


class PythonDistributionSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):
        return {
            "package_name": instance.key.package_name,
            "version": instance.key.version,
            "distribution_type": instance.key.distribution_type,
            "python_requirement": instance.key.requires_python,
            "platform_requirement": instance.key.platform,
            "abi": instance.key.abi,
            "requires": instance.value.requires,
        }

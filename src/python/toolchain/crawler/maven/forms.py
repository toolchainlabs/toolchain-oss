# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.forms import CharField

from toolchain.django.forms.base_form import ToolchainForm
from toolchain.packagerepo.maven.coordinates import GAVCoordinates


class ArtifactVersionFormBase(ToolchainForm):
    group = CharField()
    artifact = CharField()
    version = CharField()


class InvokeIndexerForm(ArtifactVersionFormBase):
    heading = "Select artifact version to index:"
    submit_text = "Index"
    class_prefix = "invoke-indexer-form"

    def __init__(self, *args, **kwargs):
        kwargs["label_suffix"] = ""  # Drop the ':' suffix, since we use the label as a placeholder in text inputs.
        super().__init__(*args, **kwargs)

    def get_gav_coords(self):
        return GAVCoordinates(
            group_id=self.cleaned_data["group"],
            artifact_id=self.cleaned_data["artifact"],
            version=self.cleaned_data["version"],
        )

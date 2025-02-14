# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.crawler.maven.models import LocateParentPOM
from toolchain.crawler.maven.workers.pom_processor import POMProcessor
from toolchain.packagerepo.maven.artifact_locator import ArtifactLocator
from toolchain.packagerepo.maven.models import POM


class ParentPOMLocator(POMProcessor):
    """Locates the parent POM of a POM file, and causes it to be fetched.

    Note that this worker doesn't actually do any fetching.  It merely finds the URL of the parent POM (if any), and
    recurses on it.  The actual fetch happens because every LocateParentPOM work unit has a requirement on a
    corresponding FetchURL work unit.
    """

    work_unit_payload_cls = LocateParentPOM

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Note that we need both these fields, as we have three states:
        # - url=None, pom=None: There is no parent.
        # - url=<url>, pom=None: There is a parent, but we haven't (recursively) fetched it yet.
        # - url=<url>, pom=<pom instance>: There is a parent, and it's been (recursively) fetched.
        self._parent_url = None
        self._parent_pom = None

    def process_pom(self):
        parent_gav_coords = self.gav_coordinates_from_xml("./parent")
        # We know of one case where a POM references itself as its parent, so
        # we skip the parent fetch in that case.  We know of no cases of indirect
        # circular parenthood, and checking for that would be more elaborate, so we don't.
        if parent_gav_coords and parent_gav_coords != self.get_gav_coordinates():
            self._parent_url = ArtifactLocator.pom_url(parent_gav_coords)
            try:
                self._parent_pom = POM.objects.get(web_resource__url=self._parent_url)
            except POM.DoesNotExist:
                return False  # Parent not fetched yet, so reschedule.
        return True

    def on_success(self, work_unit_payload):
        # Note that the POM we create is for the child whose parent we requested, which
        # we can do now that we have the parent.
        POM.update_or_create(self.get_gav_coordinates(), self.web_resource, self._parent_pom)

    def on_reschedule(self, work_unit_payload):
        if self._parent_url:
            # If we have the parent URL, it means that the superclass completed its part of do_work
            # successfully, so we're the ones that returned False from do_work() [via process_pom()].
            # This indicates that the parent POM hasn't been fetched, so now ensure we depend on that.
            parent_pom_fetch = self.schedule_util.schedule_parent_pom_fetch(self._parent_url)
            self.schedule_util.set_requirement(work_unit_payload, parent_pom_fetch)
        else:
            # The superclass was the one that returned False from do_work(), so let it handle the rescheduling.
            super().on_reschedule(work_unit_payload)

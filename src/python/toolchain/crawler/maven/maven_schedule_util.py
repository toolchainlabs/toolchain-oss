# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.conf import settings

from toolchain.crawler.base.schedule_util import ScheduleUtil
from toolchain.crawler.maven.models import ExtractPOMInfo, LocateParentPOM, ProcessLinkPage, ProcessMavenMetadata

logger = logging.getLogger(__name__)


class MavenScheduleUtil(ScheduleUtil):
    """Helper class to schedule various types of maven-related work.

    Also schedules any requirements that are known in advance. Note that this is just an optimization: The workers will
    notice if any requirements aren't met, and reschedule themselves accordingly.
    """

    def schedule_link_page_processing(self, web_resource):
        """Helper function to schedule processing a link page.

        :param web_resource: The link page's WebResource.
        :return: A ProcessLinkPage work unit instance.
        """
        return self.schedule_webresource_work(ProcessLinkPage, web_resource)

    def schedule_maven_metadata_processing(self, web_resource):
        """Helper function to schedule processing a maven-metadata.xml file.

        :param web_resource: The metadata file's WebResource.
        :return: A ProcessMavenMetadata work unit instance.
        """
        return self.schedule_webresource_work(ProcessMavenMetadata, web_resource)

    def schedule_parent_pom_fetch(self, web_resource):
        """Helper function to schedule fetching the parent of a POM file.

        :param web_resource: The POM file's WebResource.
        :return: A LocateParentPOM work unit instance.
        """
        return self.schedule_webresource_work(LocateParentPOM, web_resource)

    def schedule_extract_pom_info(self, web_resource):
        """Helper function to schedule extracting info from a POM file.

        :param web_resource: The POM file's WebResource.
        :return: An ExtractPOMInfo work unit instance.
        """
        if not settings.PROCESS_POM_FILES:
            return None
        extract_pom_info = self.schedule_webresource_work(ExtractPOMInfo, web_resource)
        parent_pom_fetch = self.schedule_parent_pom_fetch(web_resource)
        self.set_requirement(extract_pom_info, parent_pom_fetch)
        return extract_pom_info

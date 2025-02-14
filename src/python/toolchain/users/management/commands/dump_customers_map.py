# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

from django.core.management.base import BaseCommand

from toolchain.django.site.models import Customer


class Command(BaseCommand):
    help = "Dump customers map to a json file"

    def handle(self, *args, **options):
        customers_map = {customer.id: customer.slug for customer in Customer.objects.all()}
        print("customers map:")
        print(json.dumps(customers_map, indent=4))

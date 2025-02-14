# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path
from django.views.generic import RedirectView

from toolchain.django.site.views.healthz import Healthz
from toolchain.django.site.views.well_known import get_robots_txt_dynamic, get_well_known_urls
from toolchain.infosite.views import AboutUsView, PageNotFound, PricingView, ads_txt, get_infosite_template_view
from toolchain.util.metrics.prometheus_integration import prometheus_metrics_view

# Via https://codepen.io/genarocolusso/pen/XWbGMLp until we get a custom one made for us.
handler404 = PageNotFound.as_view()


urlpatterns = get_well_known_urls() + [
    path("healthz", Healthz.as_view(), name="healthz"),
    path("metricsz", prometheus_metrics_view, name="prometheus-django-metrics"),
    path("about", AboutUsView.as_view(), name="about"),
    # path("jobs", get_infosite_template_view("careers"), name="jobs"),
    path("jobs", RedirectView.as_view(url="/"), name="jobs"),
    path("privacy", get_infosite_template_view("privacy_policy"), name="privacy"),
    path("terms", get_infosite_template_view("terms_of_use"), name="terms"),
    path("product", get_infosite_template_view("product", add_meta_tags=True), name="product"),
    path("contact", get_infosite_template_view("contact", add_meta_tags=True), name="contact"),
    get_robots_txt_dynamic(),
    path("ads.txt", ads_txt, name="ads-txt"),
    path("policy", get_infosite_template_view("policy"), name="policy"),
    path("security", get_infosite_template_view("security"), name="security"),
    path("customer-agreement", get_infosite_template_view("customer-agreement"), name="customer agreement"),
    path("pricing", PricingView.as_view(), name="pricing"),
    path("", get_infosite_template_view("home", add_meta_tags=True), name="home"),
]

# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

resource "aws_route53_record" "mx_toolchain_com" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "toolchain.com"
  type    = "MX"
  ttl     = "86400"
  records = [
    "1 ASPMX.L.GOOGLE.COM.",
    "10 ASPMX2.GOOGLEMAIL.COM.",
    "10 ASPMX3.GOOGLEMAIL.COM.",
    "5 ALT1.ASPMX.L.GOOGLE.COM.",
    "5 ALT2.ASPMX.L.GOOGLE.COM.",
  ]
}

resource "aws_route53_record" "mx_toolchainlabs_com" {
  zone_id = aws_route53_zone.toolchainlabs_com.zone_id
  name    = "toolchainlabs.com"
  type    = "MX"
  ttl     = "86400"
  records = [
    "1 ASPMX.L.GOOGLE.COM.",
    "10 ASPMX2.GOOGLEMAIL.COM.",
    "10 ASPMX3.GOOGLEMAIL.COM.",
    "5 ALT1.ASPMX.L.GOOGLE.COM.",
    "5 ALT2.ASPMX.L.GOOGLE.COM.",
  ]
}

resource "aws_route53_record" "ns_toolchain_com" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "toolchain.com"
  type    = "NS"
  ttl     = "172800"
  records = [
    "ns-900.awsdns-48.net.",
    "ns-1434.awsdns-51.org.",
    "ns-477.awsdns-59.com.",
    "ns-1748.awsdns-26.co.uk.",
  ]
}

resource "aws_route53_record" "ns_toolchainlabs_com" {
  zone_id = aws_route53_zone.toolchainlabs_com.zone_id
  name    = "toolchainlabs.com"
  type    = "NS"
  ttl     = "172800"
  records = [
    "ns-2035.awsdns-62.co.uk.",
    "ns-1072.awsdns-06.org.",
    "ns-693.awsdns-22.net.",
    "ns-347.awsdns-43.com.",
  ]
}

resource "aws_route53_record" "ns_toolchain_build" {
  zone_id = aws_route53_zone.toolchain_build.zone_id
  name    = "toolchain.build"
  type    = "NS"
  ttl     = "172800"
  records = [
    "ns-435.awsdns-54.com.",
    "ns-1034.awsdns-01.org.",
    "ns-1912.awsdns-47.co.uk.",
    "ns-996.awsdns-60.net.",
  ]
}

resource "aws_route53_record" "soa_toolchain_com" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "toolchain.com"
  type    = "SOA"
  ttl     = "900"
  records = ["ns-900.awsdns-48.net. awsdns-hostmaster.amazon.com. 1 7200 900 1209600 86400"]
}

resource "aws_route53_record" "soa_toolchainlabs_com" {
  zone_id = aws_route53_zone.toolchainlabs_com.zone_id
  name    = "toolchainlabs.com"
  type    = "SOA"
  ttl     = "900"
  records = ["ns-2035.awsdns-62.co.uk. awsdns-hostmaster.amazon.com. 1 7200 900 1209600 86400"]
}

resource "aws_route53_record" "soa_toolchain_build" {
  zone_id = aws_route53_zone.toolchain_build.zone_id
  name    = "toolchain.build"
  type    = "SOA"
  ttl     = "900"
  records = ["ns-435.awsdns-54.com. awsdns-hostmaster.amazon.com. 1 7200 900 1209600 86400"]
}

locals {
  dkim_record = "v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAslhV64sVpGCLhyMIMjiaMQqBjiAKodq9FKUfzx28h1QLkJjZP1KFTE7/LZBpeP1Ma64S4ng8A9fUwbDgznuj1mgfVjeJuTrrx2m1iBb6f0TpWmlc4a5uDhokBMAmgxsRmwAnKfHp7aZg1hwdtIcA9GttvypsctgERy+oH4T5T4EbHQVgJ2kSfB2ZKSxPLpdZ8AIRm1p2/u41VeHA4SfSxsHnOx2shc2/dPzfxUdulRHtb9ppIGhOhLBSyoLG8xjT0Tkd9d8GFTkjtXCQPlj6UwKnTFy8jMuga0dCSc+x8sYrNToYteW0RN3LdkclK8E4XuqdLqm0PjGoaPuSQR0ldQIDAQAB"
}

resource "aws_route53_record" "toolchain_com_dkim" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "google._domainkey.toolchain.com."
  type    = "TXT"
  ttl     = "300"
  records = [
    # Route53 limits txt records to 255 characters. Per the AWS docs:
    #   For values that exceed 255 characters, break the value into strings of 255 characters or less.
    #   Enclose each string in double quotation marks (") using the following syntax:
    #   Domain name TXT "String 1" "String 2" "String 3"….."String N".
    # For this terraform hack for doing so, see:
    # https://github.com/hashicorp/terraform-provider-aws/issues/14941#issuecomment-934382701
    replace(local.dkim_record, "/(.{255})/", "$1\"\"")
  ]
}

resource "aws_route53_record" "txt_toolchain_com" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "toolchain.com"
  type    = "TXT"
  ttl     = "3600"
  records = [
    "v=spf1 include:_spf.google.com ~all",
    "stripe-verification=2014ad7e188063c239b17923826408f8a7eaf55070e5b023e6abe88c9f28607f",
    "proxy-ssl.webflow.com"
  ]
}

resource "aws_route53_record" "redirect_to_www_via_webflow" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "toolchain.com"
  type    = "A"
  ttl     = "300"
  records = [
    "75.2.70.75",
    "99.83.190.102",
  ]
}

resource "aws_route53_record" "www_to_webflow" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "www.toolchain.com."
  type    = "CNAME"
  ttl     = "300"
  records = ["proxy-ssl.webflow.com"]
}

resource "aws_route53_record" "github_verification" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "_github-challenge-toolchainlabs.toolchain.com."
  type    = "TXT"
  ttl     = "300"
  records = ["9b2bda85f0"]
}

resource "aws_route53_record" "readme_docs" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "docs.toolchain.com."
  type    = "CNAME"
  ttl     = "300"
  records = ["ssl.readmessl.com"]
}

resource "aws_route53_record" "new_website_cname" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "new.toolchain.com."
  type    = "CNAME"
  ttl     = "300"
  records = ["proxy-ssl.webflow.com"]
}

resource "aws_route53_record" "toolchain_com_bing_verification" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "4bbc65356f0fd172af5532453b893efc.toolchain.com"
  type    = "CNAME"
  ttl     = "900"
  records = ["verify.bing.com"]
}

resource "aws_route53_record" "dev_es_custom_endpoint" {
  zone_id = aws_route53_zone.toolchainlabs_com.zone_id
  name    = "dev-es.toolchainlabs.com"
  type    = "CNAME"
  ttl     = "900"
  records = ["vpc-es-dev-1-rk4lyznh7j3ckq2gp7impmend4.us-east-1.es.amazonaws.com"]
}

data "aws_elasticsearch_domain" "logging_prod" {
  domain_name = "prod-logging"
}

resource "aws_route53_record" "prod_logging_es_custom_endpoint" {
  zone_id = aws_route53_zone.toolchainlabs_com.zone_id
  name    = "logging.toolchainlabs.com"
  type    = "CNAME"
  ttl     = "900"
  records = [data.aws_elasticsearch_domain.logging_prod.endpoint]
}

# Verification records so Stripe can send emails from billing.toolchain.com
# https://stripe.com/docs/email-domain
locals {
  stripe_cname_map = {
    "nt5b4dfiwhnbavfosu5pcsy2sunij4yf._domainkey.billing.toolchain.com" = "nt5b4dfiwhnbavfosu5pcsy2sunij4yf.dkim.custom-email-domain.stripe.com."
    "upix4kheyo4boq3izbcar27mdedf5h6w._domainkey.billing.toolchain.com" = "upix4kheyo4boq3izbcar27mdedf5h6w.dkim.custom-email-domain.stripe.com."
    "3jtzbqpqgpghqy3v64emf5iejuqkxons._domainkey.billing.toolchain.com" = "3jtzbqpqgpghqy3v64emf5iejuqkxons.dkim.custom-email-domain.stripe.com."
    "msyhip3uwgs5jion5lauwjazqoc7l6bx._domainkey.billing.toolchain.com" = "msyhip3uwgs5jion5lauwjazqoc7l6bx.dkim.custom-email-domain.stripe.com."
    "cixsnyvfve4ukahap6ug3rudjd2jed6j._domainkey.billing.toolchain.com" = "cixsnyvfve4ukahap6ug3rudjd2jed6j.dkim.custom-email-domain.stripe.com."
    "ptzck2yfwazwm34nxsvntzle7xwzcvzi._domainkey.billing.toolchain.com" = "ptzck2yfwazwm34nxsvntzle7xwzcvzi.dkim.custom-email-domain.stripe.com."
    "bounce.billing.toolchain.com"                                      = "custom-email-domain.stripe.com."
  }
}

resource "aws_route53_record" "billing_toolchain_com_stripe_email_domain_verification" {
  for_each = local.stripe_cname_map
  zone_id  = aws_route53_zone.toolchain_com.zone_id
  name     = each.key
  type     = "CNAME"
  ttl      = "900"
  records  = [each.value]
}

resource "aws_route53_record" "billing_toolchain_com_stripe_txt_verification" {
  zone_id = aws_route53_zone.toolchain_com.zone_id
  name    = "billing.toolchain.com"
  type    = "TXT"
  ttl     = "900"
  records = ["stripe-verification=71a0c1fe44ec406329dc55e64629afac89a5891b2805d80b075d8c65d640f8d4"]
}

# Verification records so SendGrid can send emails from toolchain.com
locals {
  sendgrid_cname_map = {

    # Domain auth
    # https://docs.sendgrid.com/ui/account-and-settings/how-to-set-up-domain-authentication
    "em2155.toolchain.com"          = "u26793829.wl080.sendgrid.net"
    "TCL._domainkey.toolchain.com"  = "TCL.domainkey.u26793829.wl080.sendgrid.net"
    "TCL2._domainkey.toolchain.com" = "TCL2.domainkey.u26793829.wl080.sendgrid.net"

    # Link Branding 
    # https://docs.sendgrid.com/ui/account-and-settings/how-to-set-up-link-branding
    "url856.email.toolchain.com"   = "sendgrid.net"
    "26793829.email.toolchain.com" = "sendgrid.net"
  }
}

resource "aws_route53_record" "toolchain_com_sendgrid_email_domain_verification" {
  for_each = local.sendgrid_cname_map
  zone_id  = aws_route53_zone.toolchain_com.zone_id
  name     = each.key
  type     = "CNAME"
  ttl      = "900"
  records  = [each.value]
}

resource "aws_route53_record" "prod_graphmyrepo_google_verification" {
  zone_id = aws_route53_zone.graphmyrepo_com.zone_id
  name    = "graphmyrepo.com"
  type    = "TXT"
  ttl     = "900"
  records = ["google-site-verification=X7lxzz4zcJ3D0iFUl1T-bUTJcyCYz9neykZR9KW9Jq8"]
}

resource "aws_route53_record" "prod_graphmyrepo_bing_verification" {
  zone_id = aws_route53_zone.graphmyrepo_com.zone_id
  name    = "73dea98b8a8244c69e9ef80e842647cd.graphmyrepo.com"
  type    = "CNAME"
  ttl     = "900"
  records = ["verify.bing.com"]
}

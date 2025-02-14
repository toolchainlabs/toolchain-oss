# Blocking scanners/bots

## Introduction

From time to time, our various web properties are getting scannd by internet vulnerability scanners and malicous actors trying to see if they can hack our web properties.

This can result in alerts like `NotFoundErrorResponseRate` (a specific alert in HTTP 404 error) or `ErrorResponseRate` (a more generic alert on other HTTP 40x errors).

When the alert shows up in slack, it will include the name of the external service being scanned (service router, webhooks, etc...).

Note that we configured `NotFoundErrorResponseRate` to not fire for our marketing web sites (pants demo site and infosite), since those sites have higher visibility and get scanned all the time.
For service router (for example), we do want to alert on it since a 404 can in some cases indicate an actual issue with our web app.

## Mitigating

There is a saved search that can be accessed on the [production logging dashboard](https://logging.toolchainlabs.com/_dashboards) called `external-nginx-scans` which will show those scans.
It should be pretty clear from looking at the `logJson.uri` column in that seartch of those are scans or legitmate issue with our web app.

In all cases we observed, those scans will come from a single IP (also visible in the same search).

So the easiest thing and recommended thing to do is to block that IP from accessing our systems.
We use [AWS WAF](https://aws.amazon.com/waf/) which is configured to be attached to our internet facing loadbalancers.

In order to block a specific IP, access the [AWS WAF dashboard](https://us-east-1.console.aws.amazon.com/wafv2/homev2/start?region=us-east-1) and go to the [IP sets](https://us-east-1.console.aws.amazon.com/wafv2/homev2/ip-sets?region=us-east-1) item in the sidebar menu.
There will be a IP set called [bad-ips](https://us-east-1.console.aws.amazon.com/wafv2/homev2/ip-set/bad-ips/8f5443e1-e262-4e69-bc1e-605608b9f591?region=us-east-1), click through to that IP set and then "Add IP address".
Add the IP address from the search results in a CIDR format. For example, if the IP is `77.77.213.14` add `77.77.213.14/32`

# Google Auth

This page describes how to set up google auth (on the Google side)

We use Google auth (With the `@toolchain.com` email address) to allow engineers to access various resources:

* Kibana - for ES domains in PROD & DEV
* Grafana

## Setting up google auth for applications

* This requires special permissions on the [Google Cloud Platform Console](https://console.cloud.google.com/).

Login to the Google Cloud Console, make sure you are using your Toolchain account and not your personal account.
If you are not a full admin, you will be seeing errors unless a project you have accces to is selected.

Use the project selector on the top of the page to select a project.
Currently, we have to relevant projects:

* Kibana - For ES/Kibana auth - configured via Amazon Cognito
* Grafana - Configured as part of the Grafana chart since grafana support nativly support Google auth.

On the google console, select: API & Services -> Credentials.
You will see a "OAuth 2.0 Client IDs" table.
This is where we manage the oauth settings.
On the client page you have the Client ID & Client Secret which the application that wants to use google auth needs.
The URIs & Authorized redirect URIs should have the relevant URLs, this is a combination of the host name the client app runs under (for example: grafana.toolshed.com) and a path that the client app specifies for callback redirects.

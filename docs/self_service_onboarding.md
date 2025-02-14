# Self Service onboarding

## Background

This is the mechanism that allows customers/users to onboard to the Toolchain SaaS platform (Remote Cache & Buildsense) without requiring the intervention or help of a Toolchain employee.

The self service onbarding refers to the process of creating a customer object (which maps to a GitHub organization) and allowing users from that org access to the Toolchain Platform.
It does not cover the process of repo onboarding (adding buildsense and remote cache to a repo) other than the Repo objects creation which is can be handled by the GitHub integration.

## High level overview

There are a few components that participate in this mechanism and they are implemented in the following services:

* Service router
* Users service
* Scm integration service - specifically the GitHub integration
* Payment service - Both the Stripe integration and amberflo integration are under this service

## Flows

### User onboarding

Any Github user can now access the Toolchain SaaS, the only exception here is that if the user was deactivated (from Toolshed or otherwise) and they try to login, they will not be allowed to access and will be redirected to an access denied page.
Once a user logs in (and accepts the TOS) we redirect them to [our main page](https://app.toolchain.com/) which will try to load the SPA. However, the service router will check if the user is associated with an active customer, and if they are not, the user will be redirected to a special page [no org page](https://app.toolchain.com/org/) which will show some guidance and will instruct them to install the [Toolchain GitHub Application](https://github.com/apps/toolchain-build-system/) into their GitHub org (although gh apps can also be installed into personal user accounts we currently don’t support it).

If the user clicks the "Link an organization" we will log them out of the Toolchain app (deleting the refresh token cookie) and will redirect them to Github to start the installation of the Toolchain Github App.

The reason we log them out is that is that when they come back and re-login we will be able to call the github API (we only do that when the user logs via github) and update their customer associations and possible associate them with a new customer that was created.

### Customer onboarding

When the Toolchain GitHub Application gets installed we get a webhook from GitHub which will in turn cause us to create a customer object and repos (that webhook contains info about the repos the user chose to associate with the GitHub app).

### Repo creation and onboarding

For each repo that the user selected we will create a configure repo workflow object which will call the GitHub API in order to install a repo webhook that will notify our system about Pull Requests, Push related events.
Installing (and uninstalling) the Toolchain GitHub Application into repos can be done any time (even after onboarding) and there is logic to configure those repos when that happens.

### Stripe onboarding

#### Overview

We use [Stripe](https://stripe.com/) for payment processing (accepting payments from customers and handling invocing, payment methods, etc...)
Specifcally. we use [Stripe's Billing product](https://stripe.com/billing) which allows us to manage subscriptions.

The stripe integration leverages the [Workflow App](../src/python/toolchain/workflow/README.md) and has the following objects:

* `PeriodicallyCreateStripeCustomerSync`: Workflow payload, `StripeCustomerSyncCreator` Workflow Worker
* `PeriodicallySyncStripeCustomer`: Workflow payload, `PeriodicStripeCustomerSyncer` Workflow Worker

#### Details and Flow

We have a periodic workflow task (`PeriodicallyCreateStripeCustomerSync` & `StripeCustomerSyncCreator`) that will check for new Customer objects in the DB every few minutes (we have to poll the DB since we don't have a pub-sub mechanism/infra).
For each customer a `PeriodicallySyncStripeCustomer` will be created.

The logic in `PeriodicStripeCustomerSyncer` will only process paying customer types (currently PROSPECT & CUSTOMER and will ignore other customer types like OPEN SOURCE, INTERNAL, etc...)
The `PeriodicStripeCustomerSyncer` worker runs periodically and handles the following tasks:

* Create the Stripe customer object (if it doesn't exist)
* Create the `SubscribedCustomer` object which is our local object we use to store some stripe data locally (stripe customer id, subscription id, etc...)
* Create and "start" a Trial subscription based on our Starter Plan (our basic plan).
* Check the subsription status on the stripe side (active, canceled, trial ended) and updates the main Customer object to reflect that. Currently there are a few paths, note that this logic also triggers from a stripe webhook (subscription update):

  * Customer that ended trial and started paying will update the customer type from PROSPECT to CUSTOMER (which in turn, will cause the UI to remove the banner indicating the customer/org is in free trial)
  * if the subscription is in canceled, past due, unpaid states we will modify the `service_level` field on the customer object to `LIMITED` which will in turn cause a banner to show and will make the site readonly for that customer (no buildsense data ingestion and no access to remote cache).
    *note* that there is is an "incomplete" state for the stripe subscription which will treat as active (this is the status during the grace period in case a payment was missed)

#### Amberflo onboarding

We use the [Amberflo](https://www.amberflo.io/) platform to collect high level metrics (collected from the remote cache itself) so we can keep track remote cache usage patterns for each customer.

The logic here is similar to the Stripe onboarding logic, which means there is worker that will periodically check for new customer objects in the DB and then create an amberflo sync object for each of them.
The amberflo sync object will in turn create an amberflo customer object (for all customer types) via the amberflo API.

# Toolchain Shared Milestones

## Overview

See
[Eng Project Tracking](https://docs.google.com/document/d/1AJGzYSjT9Rwr-CaP15ridDf8m0mBtqMb1SiI4Fwd46k/edit)
for a description of the milestone process.

## Shared Milestones

### \[invisible\]

**Allowlisted users can write to BuildSense and read/write Caching**

This milestone allows us to use caching for more "alpha"/"early-access" users in
non-`pantsbuild`/`toolchain` repositories, while silently gathering data to BuildSense (ie: those
users will not be able to view BuildSense).

This milestone will enable debugging and optimization of Caching in more real world scenarios. It
also has the benefit that we will be gathering data from users that can be used to better understand
usage patterns in BuildSense.

The selection criteria for `[invisible]` users will focus primarily on:

1. the engineering effort involved in supporting authentication token acquisition in their
   environments.
1. whether their usecases are sufficiently unique or general to gain useful information for remote
   Caching.

### \[visible\]

**Allowlisted users can view BuildSense as readonly to see the benefits of Caching**

This is an important milestone for the company, because it will represent the point at which we are
comfortable showing off BuildSense and Caching together in order to begin gathering beta users for
BuildSense.

At this milestone, BuildSense will be ready to "demo" to potential beta users, by showing off the
integration with the Pantsbuild repository (or other open source repositories). Because these users
will not have their own repositories onboarded, we refer to this milestone as "read only". A small
number of users will already have been onboarded to Caching during `[invisible]`, and for those
users this milestone will primarily involve giving them access to "all of Buildsense" for their
repositories.

An assumption of these milestones is that we will not want to onboard lots of users to Caching
(exclusively) before we also have BuildSense ready to demonstrate its value (and vice versa).

### \[beta\]

**Beta users can read/write to BuildSense**

This milestone involves "launching" Buildsense and Caching in beta, and attempting to get press
about the product as a whole. Neither self-service onboarding nor billing are necessary to launch,
but we should expect to need an easier onboarding flow than was feasible at `[visible]`, and to
support roughly 10x the users we had at `[visible]`.

This milestone requires only Caching, but before the `[mvp]` milestone we will need to decide
whether Caching alone provides enough value to users to satisfy an MVP, or whether our default
product offering should incorporate Remoting.

Because of this, after the `[beta]` milestone we should onboard only enough customers to make the
product and engineering decisions to define our `[mvp]`. Consequently, Caching and BuildSense should
be only as polished and scalable as is necessary to work with beta users to decide what the MVP
should contain.

### \[mvp\]

**Users are willing and able to pay for BuildSense and a Remoting product**

This milestone represents the point at which people are willing and able to pay for Toolchain's
product, because:

1. they are convinced of the value of BuildSense
1. they are convinced of the value of Remote Caching OR Remoting

`[visible]` and `[beta]` require only Remote Caching. But in order to complete the `[mvp]`, we
should determine whether Remote Execution is a necessary component of our MVP. It's possible that in
order to provide enough value to users, we will need to implement Remote Execution, and we should
not invest significantly in polish for Caching until we have determined whether that is the case.

_This file is formatted with `mdformat --wrap 100`_

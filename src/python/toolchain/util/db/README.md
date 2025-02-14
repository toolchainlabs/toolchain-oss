# Postgres Database Roles

## Background

A PostgreSQL _role_ is an entity that can own database objects and have database privileges.
A role can be considered a "user", a "group", or both, depending on how it is used:

- A user is simply a role with a password and the LOGIN attribute.
- A group is a role to which other roles are granted membership.

A role automatically inherits the privileges of a group it is a member of, if it has the INHERIT attribute.
If it does not have this attribute, it can still issue a `SET ROLE <group>` command, which acts like `su`.

The important difference between these two cases is that any objects created by a role using privileges it
inherited are owned by that role. Whereas any objects created after `SET ROLE <group>` are owned by the group role.

See the [PostgreSQL documentation](https://www.postgresql.org/docs/11/user-manag.html) for more details.

## Our role setup

Our apps use various logical postgresql databases (e.g., a users database, a buildsense database etc.)

Each of these might be in entirely separate database clusters in production, or be separate logical databases
in the same dev database instance. Either way, each logical database must be owned by some role.
That role becomes the owner of all objects created in the database.

To facilitate credentials rotation, each logical database has two sets of associated roles:
a single owner role, and one or more login roles.

The owner role is long-lived (it's created on database creation and is expected to exist for the life of the database).
It has no password and does not have the LOGIN attribute, so it cannot be used to connect to the database.
This role owns all the objects in the logical database.

Login roles are created periodically. A login role has a password and the LOGIN attribute, and is a
non-INHERITing member of the owner role. Its only directly-assigned privilege is to CONNECT to the
logical database. After that, it must then SET ROLE to the owner role in order to access any data.

The result is that we can rotate credentials by creating new login roles and retiring old ones,
without affecting ownership of database objects.

## Creds storage

We store database creds in [secrets storage](/src/python/toolchain/util/secret/README.md).
Production and dev db creds are stored as Kubernetes secrets.
Local db creds are stores as local secrets.

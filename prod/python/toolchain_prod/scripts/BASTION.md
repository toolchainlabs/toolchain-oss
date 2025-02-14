# How to SSH Into the Bastion Host

## Prerequisites

- You need an AWS IAM user.
- That user must be in the `prod_ssh_users` IAM group.
- You must upload your public SSH key to your AWS IAM user account.

### Upload SSH key

To manually upload:

1. Go to <https://console.aws.amazon.com/iam/home>.
1. Click "Users", then your name.
1. Open the "Security credentials" tab and find the button to upload a public SSH key.

Alternatively, you can use Keymaker:

```bash
> pip install keymaker
> keymaker upload_key --identity /path/to/key/file
```

If you only have one identity on your machine, you can omit the `--identity /path/to/key/file` part.

If the key file is a private key, Keymaker will generate a public key from it.

## Setting SSH Agent Forwarding

In order to jump/ssh from the bastion host to other hosts, you must enable SSH Agent Forwarding by adding `ForwardAgent yes` to your `~/.ssh/config`.

For example:

```bash
Host *.toolchainlabs.com *.toolchain.private
  ForwardAgent yes
```

## Setting the Remote User Name

If your toolchainlabs username is not the same as the one on your local machine, you can set
the default username for the remote machine by adding something like this into your `~/.ssh/config`:

```bash
# For example, my local user is parzival, but toolchainlabs expects wadew.
#
# Note that if accessing an internal host via a jump through the bastion (e.g., using ssh -J),
# the user for that host is resolved here, not on the bastion. So we must also set the user for
# the various ways we could address that host (our private DNS, ec2's private DNS, or private IP).
Host *.toolchainlabs.com *.toolchain.private *.ec2.internal 10.*
  User wadew
  IdentitiesOnly yes
```

## Extra Privileges

- To have sudo privileges on prod machines, you need to be in the IAM group `linux_sudo`.
- To use docker on prod machines, you need to be in the IAM group `linux_docker`.

## SSH to the Bastion

You must be connected to the [VPN](../../../VPN.md) in order to connect to the bastion host.

```shell
ssh bastion.toolchain.private
```

Which points to a canonical bastion host.

The first time you connect to a host you'll get this error:

```shell
Keymaker: Your user account has been replicated to this host but cannot be used for this session.
Keymaker: Create a new SSH connection.
Password:
```

This means that you had no user on that host, but one is being created for you.

Just `ctrl-c` out and re-run the same SSH command, and you should be in.

## SSH From the Bastion to Another Host

You typically want to SSH into another host. Find its internal IP or DNS name, and simply

```shell
ssh [ip or hostname]
```

on the bastion.

E.g.,

```shell
ssh devbox.toolchain.private
```

to reach that devbox.

Again, the first time you connect to a host you'll get the error mentioned above, and the solution is the same.

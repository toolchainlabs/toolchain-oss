# Toolchain VPN

## Connecting & Logging in

* Go to <https://tcvpn.toolchainlabs.com> and login.
* We use [Duo](https://duo.com/) for 2FA with open VPN. You will need to download and install their mobile app. For [iPhone](https://itunes.apple.com/us/app/duo-mobile/id422663827?mt=8) or [Android](https://play.google.com/store/apps/details?id=com.duosecurity.duomobile&hl=en).
* You might need to enroll in duo, which is our 2FA solution. Download the Duo app to the mobile phone is required.

> You can not use a different 2FA app such as Google Authenticator or Authy since, we will be using [Duo Push](https://duo.com/product/multi-factor-authentication-mfa/authentication-methods/duo-push) (not with OpenVPN though) and the Duo Mobile app is required for that.

* After the user/password you will be prompted for a 2FA code, which will be in the Duo App.
* Download the relevant client software from the [OpenVPN Web UI home page](https://tcvpn.toolchainlabs.com/?src=connect) and then get the auto-login profile (near the bottom of the page there is a `Available Connection Profiles` section), open it with the OpenVPN client.

**Note**: Don't keep your VPN client connected if you are not accessing resources protected by the VPN. By default (currently) all internet traffic is routed via the VPN.

In the future, we will figure out how to improve the VPN network configuring to only route certain traffic via VPN

## Adding new users

* Only users designated as OpenVPN Admins can add users.
  Current VPN Admins:
  * Asher Foa
  * Benjy Weinberger
  * John Sirois

* [OpenVPN Admin UI](<https://tcvpn.toolchainlabs.com/admin/>) is only accessible while the VPN is connected.

* Adding a VPN user is done via the OpenVPN Admin Web UI, User Management -> User Permissions
* Add a user using their toolchain username (email alias/AWS User).
* Enable the "Allow Auto-login" checkbox
* Set an initial password and share it with the user, currently there is no way to force a password change, but ask the user to do that after they log in (there is a "Change Password" button at the bottom of the page once the user logs in)
* The user might need to enroll in Duo, this is self service and an enrollment link will show up upon successful login.

## Resources requiring VPN Access

* [OpenSearch Dashboard](https://dev-es.toolchainlabs.com/_dashboards/app/home#/) dev domain - for buildsense data in dev and for dev logging
* [OpenSearch Dashboard](https://logging.toolchainlabs.com/_dashboards/) production logging
* [Grafana](https://grafana.toolchainlabs.com)
* [Not implemented yet] Bastion
* [Toolshed Admin UI](https://toolshed.toolchainlabs.com/)

## Installing OpenVPN

Currently, the OpenVPN box is more of a [pet than cattle](http://cloudscaling.com/blog/cloud-computing/the-history-of-pets-vs-cattle/), Which means there is no 1-click automation to
re-provision the OpenVPN box if it dies.

Here are how we provisioned our OpenVPN server currently:
Provisioning OpenVPN is based on this [quick start guide](https://openvpn.net/vpn-server-resources/amazon-web-services-ec2-byol-appliance-quick-start-guide/)

### Steps & Parameters

* Instance launch options, Terraform resources are in us-east-1/vpn/vpn.tf
  * Security Group 'vpn-access-server', provisioned via Terraform
  * Subnet: 'vpn-subnet', , provisioned via Terraform
  * SSH Key: 'vpn-ssh-keys' -  private key (.pem file) is in 1Password under "OpenVPN Admin User"
  * Elastic IP 'vpn_as_ip' - provisioned via & associated to the instance via Terraform.
    There is a route53 DNS record pointing to this IP, also managed via Terraform).
  * Connect to the new AMI using SSH, use `ssh-add vpn-ssh-keys.pem` to add the private key to ssh (might need to `chmod 400 vpn-ssh-keys.pem` to make file not accessible to other users)
* Open VPN Setup Wizard:
  * primary Access Server node?: YES
  * please specify the network interface and IP address to be used by the Admin Web UI: all interfaces (default)
  * Admin Web UI port: 943
  * TCP port number for the OpenVPN Daemon: Default
  * Should client traffic be routed by default through the VPN?: YES
  * Should client DNS traffic be routed by default through the VPN?: YES
  * Use local authentication via internal DB? YES
  * Should private subnets be accessible to clients by default?: YES
  * Do you wish to login to the Admin UI as “openvpn"?: NO, use the admin & pw stored in 1password.
  * OpenVPN-AS license key: leave blank (we pay via AWS Marketplace)

* Changing the host name (via the Admin Web UI, Configuration -> Network Settings): `tcvpn.toolchainlabs.com`
* Associated/import the instance into the Terraform config, it will make sure that source destination check, security groups and subnets are properly configured.
* Follow the next steps to install SSL certificate and enable integration w/ Duo.

### Installing SSL certificate

Must rename the host before doing that
We use [Let's Encrypt](https://letsencrypt.org/) certificate.
The flow is based on this [article](https://loige.co/using-lets-encrypt-and-certbot-to-automate-the-creation-of-certificates-for-openvpn/)

* Installing CertBot

```shell
sudo apt-get -y install software-properties-common && sudo add-apt-repository -y ppa:certbot/certbot && sudo apt-get -y update
sudo apt-get -y install certbot
```

* Issuing a cert, for that to work, we need to modify the security group to allow access via HTTP.
  When certbot is running it, the certbot API servers will contact the vpn access server via this HTTP port.

```shell
sudo certbot certonly --standalone --non-interactive  --agree-tos --email ops-mgmt@toolchain.com --domains tcvpn.toolchainlabs.com --pre-hook 'sudo service openvpnas stop' --post-hook 'sudo service openvpnas start'
```

* Run `terraform apply` for the vpn resource or manually remove the inbound rule allowing HTTP.

* associated the certs with the OpenVPN Web Server:

```shell
sudo ln -s -f /etc/letsencrypt/live/tcvpn.toolchainlabs.com/cert.pem /usr/local/openvpn_as/etc/web-ssl/server.crt
sudo ln -s -f /etc/letsencrypt/live/tcvpn.toolchainlabs.com/privkey.pem /usr/local/openvpn_as/etc/web-ssl/server.key
```

### Renew SSL certificate

The [Let's Encrypt](https://letsencrypt.org/) certificate expires every 3 months (180 days) so it needs to be manually renewed.
An email is sent about 20 days before it expires to ops-mgmt@toolchain.com.

The renewal process is similar to the installation process, minus installing the required certbot software:

1. In the AWS console, [EC2->Security groups](https://us-east-1.console.aws.amazon.com/ec2/v2/home?region=us-east-1#SecurityGroups:group-name=vpn-access-server), locate the `vpn-access-server` security group.

2. Edit the inbound rules to allow SSH from your [current IPv4](https://whatismyipaddress.com/), so for example if your IP is `104.1.22.71` then use the value `104.1.22.71/32` in the source column of inbound rules. changes.
3. Add the VPN SSH keys using ssh-add (the key is stored in 1password):

    ```shell
    ssh-add ~/.ssh/vpn-ssh-keys.pem
    ```

4. Connect to the vpn server via SSH:

    ```shell
    ssh openvpnas@tcvpn.toolchainlabs.com
    ```

5. Run the renew command:

    ```shell
    sudo certbot certonly --standalone --non-interactive  --agree-tos --email ops-mgmt@toolchain.com --domains tcvpn.toolchainlabs.com --pre-hook 'sudo service openvpnas stop' --post-hook 'sudo service openvpnas start'
    ```

6. Go to the [VPN web page](https://tcvpn.toolchainlabs.com/) and check that the SSL certificate is valid & renewed (i.e. the expiration date is 180 days away).

7. disconnect from SSH

8. Run `terraform apply` from the `prod/terraform/resources/us-east-1/vpn` folder to remove the inbound rules that were added.

### Two Factor Auth with Duo

Flow is based on <https://duo.com/docs/openvpn-as>

Specific steps:

```shell
sudo /usr/local/openvpn_as/scripts/sacli -a tcvpnadmin --prompt --key=auth.module.post_auth_script --value_file=/usr/local/openvpn_as/scripts/duo_openvpn_as.py ConfigPut
sudo /usr/local/openvpn_as/scripts/sacli -a tcvpnadmin --prompt Reset
```

## Configuring logo & branding

We use our logo & company name on the OpenVPN web UI.
To set this up I followed the [instructions on the OpenVPN site](https://openvpn.net/vpn-server-resources/change-the-logo-on-the-web-server-interfaces/)

## Connecting to the VPN Server via SSH

Normally, the security group rule that allows SSH connections to the VPN instance is commented out (in Terraform) thus the AWS security group doesn't allow SSH connections.
If there is a need to SSH to the VPN server instance, to do VPN maintenance (for example), add a rule to the security group, ideally, limiting the IP range based on your current IP. We should never open it to SSH connection from 0.0.0.0
Also, once the SSH rule is no longer needed, it should be removed. This can be done by running `terraform apply`.

Unlike other EC2 machines (bastion, devbox, Kubernetes nodes), we don't sync IAM users ssh keys to the VPN server.
So in order to connect, you will need to add a VPN specific SSH keys to your ssh client, the key stored in the shared 1Password Vault.
Extract it from there and add it using `ssh-add`

Then connect:

```shell
ssh openvpnas@tcvpn.toolchainlabs.com
```

## Backing up VPN DB & Config

We backup the VPN data based on the stop described [here](https://openvpn.net/vpn-server-resources/configuration-database-management-and-backups/)

SSH into the vpn server and run the following commands under sudo.

```shell
cd /usr/local/openvpn_as/etc/db
[ -e config.db ]&&sqlite3 config.db .dump>/home/openvpnas/backup/config.db.bak
[ -e certs.db ]&&sqlite3 certs.db .dump>/home/openvpnas/backup/certs.db.bak
[ -e userprop.db ]&&sqlite3 userprop.db .dump>/home/openvpnas/backup/userprop.db.bak
[ -e log.db ]&&sqlite3 log.db .dump>/home/openvpnas/backup/log.db.bak
[ -e config_local.db ]&&sqlite3 config_local.db .dump>/home/openvpnas/backup/config_local.db.bak
[ -e cluster.db ]&&sqlite3 cluster.db .dump>/home/openvpnas/backup/cluster.db.bak
[ -e clusterdb.db ]&&sqlite3 clusterdb.db .dump>/home/openvpnas/backup/clusterdb.db.bak
[ -e notification.db ]&&sqlite3 notification.db .dump>/home/openvpnas/backup/notification.db.bak 
cp ../as.conf /home/openvpnas/backup/as.conf.bak
```

Then zip/tar the backup directory.

```shell
tar czvf /home/openvpnas/vpn-backup-<date>tar.gz /home/openvpnas/backup/
```

From your mac, scp the file from the VPN server to your local machine:

```shell
scp openvpnas@tcvpn.toolchainlabs.com:/home/openvpnas/vpn*.tar.gz ~/Downloads
```

Finally, upload the backup to s3:

```shell
aws s3 cp ~/projects/vpn-backup-<date>.tar.gz s3://general.us-east-1.toolchain.com/backups/vpn/
```

**After uploading to s3, delete the backup from your local machine! don't keep it around.**

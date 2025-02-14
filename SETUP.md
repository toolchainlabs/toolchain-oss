# Client Setup

Here are some tips on getting your laptop set up for working with this repository.

## Toolchain

Tips for building and testing our own code.

### One-time setup per machine

- Install Docker

  - (macOS): Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop).

    - If Docker fails to start on login, then macOS may have quarantined it. Run the following to
    clear the issue: `xattr -d -r -s com.apple.quarantine /Applications/Docker.app`. You can see if this
    is an issue by looking in /var/log/system.log for messages like:

    ```log
    Feb 21 00:54:50 HOST com.apple.xpc.launchd[1] (com.docker.helper[43995]): Could not find and/or execute program specified by service: 155: Refusing to execute/trust quarantined program/file: com.docker.helper
    ```

  - (Linux - Ubunty/Debian): Install the `docker.io` package:
  
    ```shell
    sudo apt-get install docker.io
    ```

  - (other): Find specific instructions on how to install Docker manually on your system.

- (macOS) [Install Homebrew](https://brew.sh/):
  
  ```shell
  /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
  ```
  
  Note: This Homebrew installation will be distinct from the vendored Homebrew that this repository will setup in
  `~/.toolchain/homebrew` in a later step. This gives you the opportunity to install utilities that work when you
  are not operating within this repository, while retaining the managed environment expected by this repository.
  It is also necessary to work around an issue with `direnv`.

- Install the latest stable version of OpenJDK if not already installed on your system.

  - (macOS) Run the following commands:

    ```shell
    brew install openjdk
    # On M1 macs:
    sudo ln -sfn /opt/homebrew/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
    # On Intel macs:
    sudo ln -sfn /usr/local/opt/openjdk/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
    java -version  # this should show the version you just installed
    ```

  - (Linux) Use your system's package manager to install the latest stable version of OpenJDK.
  
  - (manual install) Visit the [official Oracle site](https://www.oracle.com/java/technologies/javase-downloads.html) or
  the [OpenJDK site](http://openjdk.java.net/install/index.html) to download and install prebuilt JDK packages.  

#### On macOS

- Update XCode command line tools (if you get errors relating to `.h` files)

  ```shell
  xcode-select --install
  ```

- Install `pyenv` into the system Homebrew before installing `direnv`. This is necessary because `direnv` requires `pyenv`
  but the setup script for this repository requires `direnv` to be functional before it installs `pyenv` into the
  vendored Homebrew.
  
  ```shell
  brew install pyenv
  ```

- Install [direnv](https://direnv.net/) which will source the `.envrc` file in this repository whenever you change
  into the root of this repository (or any other directory tree for that matter). This helps us keep our dev environments
  consistent.

  - Install direnv into the system Homebrew:

    ```shell
    brew install direnv
    ```

  - Configure your shell to activate direnv:
  
    - (bash) Add the line `eval "$(direnv hook bash)"` to your `~/.bashrc` file. (Also ensure that your
    `~/.bash_profile` sources `~/.bashrc`, otherwise login shells will not activate anything in the `.bashrc`.)
  
    - (other shells) Follow the [per-shell instructions](https://direnv.net/docs/hook.html) on the direnv website.

  - Note:

    - To override or add additional environment variables, create a `.envrc.private` file and add as you like.

    - Whenever .envrc is changed, `direnv` will alert you and require that you run `direnv allow` to enable the changes.

- *Before* cloning this repository, install [git LFS](https://git-lfs.github.com/) into the system Homebrew.
  (`git LFS` allows us to store large blobs outside of this repository.)

  ```shell
  brew install git-lfs
  ```

### GitHub setup

- Create a SSH key and add it to GitHub:

  - Run `ssh-keygen` to generate a SSH key. The public key will usually be stored in `~/.ssh/id_rsa.pub`.
  
  - Visit the [GitHub SSH keys page](https://github.com/settings/keys) to add the public key to GitHub.

- Fork this repository on GitHub.

- Add your `@toolchain.com` email address to your GitHub account at the
  [Email Settings page](https://github.com/settings/emails), and then click the confirmation link in the
  resulting verification email to validate the address.

- Authorize access to the Toolchain OAuth app for GitHub by visiting <https://app.toolchain.com/> and
  confirming access via your GitHub credentials. Note: We require a validated `@toolchain.com` email address
  associated with your GitHub account (see the prior step ...).

### One-time setup per repo per machine

- Clone this repository and your fork (replacing `USER` with your username):

  ```shell
  git clone git@github.com:toolchainlabs/toolchain.git
  cd toolchain
  git remote add $USER git@github.com:$USER/toolchain.git
  git fetch $USER 
  ```

- Run [`setup.sh`](./setup.sh) to set up git hooks, python environment, etc.

  If curious, see [`src/sh/setup/`](./src/sh/setup/) for details on what's happening here.

  :memo: In addition to `setup.sh` above, [`./python`](./python) will bootstrap the Python environment without touching git hooks or other utilities.

  :warning: On macOS, this script may fail when installing Postgres through Homebrew with `error: header file <perl.h> is required for Perl`. The solution is to run `brew edit postgresql` and change the line `--with-perl` to `--without-perl`. See <https://github.com/petere/homebrew-postgresql/issues/41#issuecomment-405048183>.

- Setup access from this repository to the Toolchain GitHub OAuth app:

  ```shell
  ./pants auth-acquire
  ```

### Getting started

- Once your environment has been set up, try running our tests (which live side-by-side with ordinary sources):

  ```shell
  ./pants test src/python::
  ```

  Note: We currently use the `./pants` wrapper script to invoke Pants, not `./pants` directly, only for Python. For
  other languages, you will still need to call `./pants` in invoke Pants.

## AWS Setup

One of the other employees with AWS admin privileges will generate a new AWS account for you and securely send you
the password. You will need to setup two-factor authentication and your command-line tools.

- Login to AWS at <https://toolchain.signin.aws.amazon.com/console> and change your password when prompted. Store the password in 1password.

  - Note: The username will be the same as your Toolchain user alias.
  ([Certain code](https://github.com/toolchainlabs/toolchain/blob/master/src/python/toolchain/prod/iam_watcher/check_iam_access_keys.py#L56)
  in this repository expects that convention.)

- Enable two-factor authentication for your AWS account by adding AWS to Google Authenticator (or similar app)
  on your phone as a "virtual MFA" device (MFA == multi-factor authentication).

  - From the `USER@toolchain' drop-down in the upper right corner, choose ["My Security Credentials"](https://console.aws.amazon.com/iam/home?region=us-east-2#/security_credentials).

  - [Follow the instructions](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable_virtual.html#enable-virt-mfa-for-own-iam-user) to add a virtual MFA device.
  
- Generate an access key for your AWS account, and configure the AWS command-line tools:

  - From the "My Security Credentials" page mentioned above, click "Create Access Key". You will be shown
    the access key and secret key.

  - Configure the AWS command-line tools with the access/secret keys by running `aws configure` and providing the access key and secret key shown to you by the AWS console. Set a default region of `us-east-1`.

  - Note: We expire AWS access keys on a regular basis. See [check_iam_access_keys.py](https://github.com/toolchainlabs/toolchain/blob/master/src/python/toolchain/prod/iam_watcher/check_iam_access_keys.py)
  for additional details.

  - Refer to [Kubernetes README](./prod/kubernetes/README.md) to confiigure access to our Kubernetes clusters running in AWS.

## Devbox

We have a Toolchain development environment setup on a "devbox" running in EC2. See the
[devbox documentation](docs/devbox.md) for more details.

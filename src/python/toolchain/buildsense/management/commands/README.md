# Buildsense Django Commands

To run these commands:

1. Connect to prod Kubernetes cluster: `./prod/kubernetes/kubectl_setup.sh prod-e1-1`
2. Set the default namespace to prod: `kubectl config set-context --current --namespace=prod`
3. Connect to a buildsense/api pod: `./src/sh/kubernetes/open_shell.sh buildsense/api`
4. Run a command with `./manage.py $command`, or view the help by running `./manage.py`

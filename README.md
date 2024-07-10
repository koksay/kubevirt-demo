# Getting Started with KubeVirt

## Bootstrap Flux

To start our GitOps journey with [Flux](https://fluxcd.io/), we need to bootstrap it first:

```bash
flux check --pre
► checking prerequisites
✔ Kubernetes 1.25.3 >=1.20.6-0
✔ prerequisites checks passed
```

If the checks are successful, you can install Flux on the cluster. First export GitHub credentials:

```bash
export GITHUB_USER=<GITHUB_USER>
export GITHUB_TOKEN=<GITHUB_TOKEN>
```

Let’s install Flux on it - if you need to use other options, check out the installation page.

```bash
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=kubevirt-demo \
  --branch=main \
  --path=./gitops/clusters/my-cluster \
  --personal
```

## Install KubeVirt operator and CR

```bash
export VERSION="v1.2.2"
export KUBEVIRT_MANIFEST_DIR="./gitops/clusters/my-cluster/kubevirt"
mkdir ${KUBEVIRT_MANIFEST_DIR}

# add files to flux
curl -L https://github.com/kubevirt/kubevirt/releases/download/${VERSION}/kubevirt-operator.yaml -o ${KUBEVIRT_MANIFEST_DIR}/kubevirt-operator.yaml
curl -L https://github.com/kubevirt/kubevirt/releases/download/${VERSION}/kubevirt-cr.yaml -o ${KUBEVIRT_MANIFEST_DIR}/kubevirt-cr.yaml

# git push to take effect
git pull
git add ${KUBEVIRT_MANIFEST_DIR}
git commit -am "Deploy KubeVirt"
git push
```

## Verify components

```bash
kubectl get kubevirt.kubevirt.io/kubevirt -n kubevirt -o=jsonpath="{.status.phase}"
```

## Wait to be ready

```bash
kubectl wait kubevirt.kubevirt.io/kubevirt -n kubevirt \
    --for=jsonpath='{.status.phase}=Deployed' --timeout=120s

kubectl get all -n kubevirt
```

## You need to install virtctl binary or krew plugin

```bash
VERSION=$(kubectl get kubevirt.kubevirt.io/kubevirt -n kubevirt -o=jsonpath="{.status.observedKubeVirtVersion}")
ARCH=$(uname -s | tr A-Z a-z)-$(uname -m | sed 's/x86_64/amd64/') || windows-amd64.exe
echo ${ARCH}
curl -L -o virtctl https://github.com/kubevirt/kubevirt/releases/download/${VERSION}/virtctl-${VERSION}-${ARCH}
chmod +x virtctl
sudo install virtctl /usr/local/bin

# or
kubectl krew install virt
```

## Create the VM via Helm Chart installation

```bash
helm upgrade --install mytestvm ./kubevirt-vm \
  --create-namespace --namespace=dev
```

## Check the VMIs

>[!TIP]
>VirtualMachine defines the desired state of a VM, while VirtualMachineInstance represents the actual running instance of the VM within Kubernetes.

```bash
kubectl get vmis -n dev
```

## Get the Private key to connect via SSH

```bash
kubectl get secret my-pri-key -n dev -o jsonpath='{.data.key1}' \
  | base64 -d > ~/.ssh/testvm && chmod 600 ~/.ssh/testvm

kubectl get secret my-pub-key -n dev -o jsonpath='{.data.key1}' \
  | base64 -d > ~/.ssh/testvm.pub && chmod 600 ~/.ssh/testvm.pub
```

Then connect using virtctl:

```bash
kubectl virt ssh -i ~/.ssh/testvm fedora@test-vm -n dev
```

Try to access to the Kubernetes API inside the cluster:

```bash
[fedora@test-vm ~]$ curl -k https://kubernetes.default.svc.cluster.local
{
  "kind": "Status",
  "apiVersion": "v1",
  "metadata": {},
  "status": "Failure",
  "message": "forbidden: User \"system:anonymous\" cannot get path \"/\"",
  "reason": "Forbidden",
  "details": {},
  "code": 403
}
```

# Getting Started with KubeVirt and ArgoCD

## Deploy ArgoCD

To start our GitOps journey with [ArgoCD](https://argoproj.github.io/cd/), we need to bootstrap it first:

```bash
# This will do a non-HA deployment. For production, you should use `manifests/ha/install.yaml` file
export ARGOCD_VERSION="v2.11.4"
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml
```

After installing Argo CD, check the installed Custom Resource Definitions:

```bash
kubectl get crd | grep argoproj
```

Wait until all pods are ready:

```bash
kubectl wait pod --all --for=condition=Ready \
  --namespace=argocd --timeout=600s
```

## Access to the UI

If you did not create the service as `LoadBalancer`, then you can port-forward and access to the UI.

First, get the `admin` password:

```bash
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath="{.data.password}" | base64 -d
```

Port forward and access via `https://localhost:8080`:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

## Install KubeVirt operator and CR

Set variables:

```bash
export VERSION="v1.2.2"
export KUBEVIRT_MANIFEST_DIR="./gitops/clusters/my-cluster/kubevirt"
export KUBEVIRT_RELEASE_URL="github.com/kubevirt/kubevirt/releases/download"
mkdir ${KUBEVIRT_MANIFEST_DIR}
```

Add files to GitOps directory:

```bash
curl -L https://${KUBEVIRT_RELEASE_URL}/${VERSION}/kubevirt-operator.yaml \
  -o ${KUBEVIRT_MANIFEST_DIR}/kubevirt-operator.yaml
curl -L https://${KUBEVIRT_RELEASE_URL}/${VERSION}/kubevirt-cr.yaml \
  -o ${KUBEVIRT_MANIFEST_DIR}/kubevirt-cr.yaml
```

Push to the repo to deploy

```bash
git add ${KUBEVIRT_MANIFEST_DIR}
git commit -m "Deploy KubeVirt"
git push
```

Add `kubevirt` application on ArgoCD:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kubevirt
  namespace: argocd
spec:
  destination:
    namespace: kubevirt
    server: "https://kubernetes.default.svc"
  project: default
  source:
    path: gitops/clusters/my-cluster/kubevirt
    repoURL: "https://github.com/koksay/kubevirt-demo"
    targetRevision: main
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF
```

## Verify components

```bash
kubectl get kubevirt.kubevirt.io/kubevirt -n kubevirt \
  -o=jsonpath="{.status.phase}"
```

## Wait to be ready

```bash
kubectl wait kubevirt.kubevirt.io/kubevirt -n kubevirt \
    --for=jsonpath='{.status.phase}=Deployed' --timeout=120s
```

Check the `kubevirt` namespace:

```bash
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

## Deploy vm-provisioner app

```bash
cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: vm-provisioner
  namespace: argocd
spec:
  destination:
    namespace: vm-provisioner
    server: "https://kubernetes.default.svc"
  project: default
  source:
    path: vm-provisioner/k8s
    repoURL: "https://github.com/koksay/kubevirt-demo"
    targetRevision: main
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF
```

## Access to the app

```bash
kubectl port-forward vm-provisioner 5000:5000
```

## Create the VM via the app

Create a VM using [vm-provisioner application](http://localhost:5000). Then download the SSH Key.

## Check the VMIs

>[!TIP]
>VirtualMachine defines the desired state of a VM, while VirtualMachineInstance represents the actual running instance of the VM within Kubernetes.

```bash
kubectl get vmis -n virtualmachines
```

## Connect to the VM via SSH

Connect using virtctl:

```bash
chmod 600 ~/Downloads/${VM_NAME}.key
kubectl virt ssh -i ~/Downloads/${VM_NAME}.key --local-ssh fedora@${VM_NAME} -n virtualmachines
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

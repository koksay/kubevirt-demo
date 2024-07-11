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
git commit -am "Deploy KubeVirt"
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

## Create the VM via Helm Chart installation

Create a `virtualmachine` application:

```bash
export VM_NAME="test-vm-1"

cat <<EOF | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ${VM_NAME}
  namespace: argocd
spec:
  project: default
  source:
    repoURL: 'https://github.com/koksay/kubevirt-demo.git'
    targetRevision: main
    path: charts/kubevirt-vm
    helm:
      releaseName: ${VM_NAME}
      valuesObject:
        vm:
          hostname: ${VM_NAME}
          memory: 1Gi
          containerDisk:
            image: quay.io/containerdisks/fedora:latest
          cloudInit:
            userData: |
              #cloud-config
              password: fedora
              chpasswd: { expire: False }
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: virtualmachines
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    automated:
      prune: true
      selfHeal: true
EOF
```

## Check the VMIs

>[!TIP]
>VirtualMachine defines the desired state of a VM, while VirtualMachineInstance represents the actual running instance of the VM within Kubernetes.

```bash
kubectl get vmis -n virtualmachines
```

## Get the Private key to connect via SSH

Private key:

```bash
kubectl get secret pri-key-${VM_NAME} -n virtualmachines -o jsonpath='{.data.key1}' \
  | base64 -d > ~/.ssh/${VM_NAME} && chmod 600 ~/.ssh/${VM_NAME}
```

Public key:

```bash
kubectl get secret pub-key-${VM_NAME} -n virtualmachines -o jsonpath='{.data.key1}' \
  | base64 -d > ~/.ssh/${VM_NAME}.pub && chmod 600 ~/.ssh/${VM_NAME}.pub
```

Then connect using virtctl:

```bash
kubectl virt ssh -i ~/.ssh/${VM_NAME} fedora@${VM_NAME} -n virtualmachines
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

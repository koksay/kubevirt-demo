from flask import Flask, render_template, request, send_file
from kubernetes import client, config
import base64
import os
import tempfile

app = Flask(__name__)

# Load Kubernetes configuration
config.load_incluster_config()

k8s_custom_client = client.CustomObjectsApi()
k8s_v1_client = client.CoreV1Api()

def get_public_key(vm_name):
    pass


@app.route('/')
def index():
    try:
        # Get the list of VMs
        vms = k8s_custom_client.list_namespaced_custom_object('kubevirt.io', 'v1', 'virtualmachines', 'virtualmachines')
        vm_names = [vm['metadata']['name'] for vm in vms['items']]
    except client.ApiException as e:
        print(str(e))

    return render_template('index.html', vm_names=vm_names)


@app.route('/submit', methods=['POST'])
def submit():
    vm_name = request.form['vm_name']
    vm_size = request.form['vm_size']

    application = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": vm_name,
            "namespace": "argocd"
        },
        "spec": {
            "project": "default",
            "source": {
                "repoURL": "https://github.com/koksay/kubevirt-demo.git",
                "targetRevision": "main",
                "path": "charts/kubevirt-vm",
                "helm": {
                    "releaseName": vm_name,
                    "valuesObject": {
                        "vm": {
                            "hostname": vm_name,
                            "memory": vm_size,
                            "containerDisk": {
                                "image": "quay.io/containerdisks/fedora:latest"
                            },
                            "cloudInit": {
                                "userData": "#cloud-config\npassword: fedora\nchpasswd: { expire: False }\n"
                            }
                        }
                    }
                }
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "virtualmachines"
            },
            "syncPolicy": {
                "syncOptions": [
                    "CreateNamespace=true"
                ],
                "automated": {
                    "prune": True,
                    "selfHeal": True
                }
            }
        }
    }

    try:
        k8s_custom_client.create_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argocd",
            plural="applications",
            body=application,
        )
        message = f"Virtual Machine {vm_name} created successfully!"
    except client.ApiException as e:
        message = f"Failed to create Virtual Machine {vm_name}: {str(e)}"

    # Pass the message to the template
    return render_template('result.html', message=message, vm_name=vm_name, vm_size=vm_size)


@app.route('/download/<vm_name>')
def download_private_key(vm_name):
    secret_name = f"pri-key-{vm_name}"
    try:
        # Fetch the secret
        secret = k8s_v1_client.read_namespaced_secret(name=secret_name, namespace='virtualmachines')
        # Decode the private key
        private_key = base64.b64decode(secret.data['key1'])

        # Create a temporary file and set the permissions
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(private_key)
            tmp_file_path = tmp_file.name

        os.chmod(tmp_file_path, 0o600)

        return send_file(tmp_file_path, as_attachment=True, download_name=f"{vm_name}.key")
    except client.ApiException as e:
        return f"Failed to download private key for {vm_name}: {e.reason}", 500    
    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


if __name__ == '__main__':
    app.run(debug=True)

#!/usr/bin/env python3
"""
ArciTEK.AI Google Cloud Deployment Configuration
Enterprise-ready deployment on Google Cloud Platform
"""

import os
import json
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeploymentEnvironment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ServiceType(Enum):
    OPTIMIZATION_ENGINE = "optimization-engine"
    MONITORING_AGENT = "monitoring-agent"
    BENCHMARK_SYSTEM = "benchmark-system"
    API_GATEWAY = "api-gateway"
    WEB_DASHBOARD = "web-dashboard"


@dataclass
class GCPConfig:
    project_id: str
    region: str
    zone: str
    cluster_name: str
    node_count: int
    machine_type: str
    disk_size_gb: int
    auto_scaling: bool
    min_nodes: int
    max_nodes: int


class GCPDeployment:
    """Google Cloud Platform deployment manager"""
    
    def __init__(self, config: GCPConfig, environment: DeploymentEnvironment):
        self.config = config
        self.environment = environment
        self.deployed_services = []
        
    def generate_kubernetes_manifests(self) -> Dict[str, str]:
        """Generate Kubernetes manifests for all services"""
        manifests = {}
        
        # Optimization Engine Deployment
        manifests['optimization-engine-deployment.yaml'] = self._create_optimization_engine_manifest()
        manifests['optimization-engine-service.yaml'] = self._create_service_manifest(
            ServiceType.OPTIMIZATION_ENGINE
        )
        
        # Monitoring Agent Deployment
        manifests['monitoring-agent-daemonset.yaml'] = self._create_monitoring_agent_manifest()
        
        # Benchmark System Deployment
        manifests['benchmark-system-deployment.yaml'] = self._create_benchmark_manifest()
        manifests['benchmark-system-service.yaml'] = self._create_service_manifest(
            ServiceType.BENCHMARK_SYSTEM
        )
        
        # API Gateway
        manifests['api-gateway-deployment.yaml'] = self._create_api_gateway_manifest()
        manifests['api-gateway-service.yaml'] = self._create_service_manifest(
            ServiceType.API_GATEWAY
        )
        manifests['api-gateway-ingress.yaml'] = self._create_ingress_manifest()
        
        # ConfigMaps and Secrets
        manifests['configmap.yaml'] = self._create_configmap()
        manifests['secrets.yaml'] = self._create_secrets()
        
        # Horizontal Pod Autoscaler
        manifests['hpa.yaml'] = self._create_hpa_manifest()
        
        return manifests
    
    def _create_optimization_engine_manifest(self) -> str:
        """Create Kubernetes deployment for optimization engine"""
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: optimization-engine
  namespace: arcitek-{self.environment.value}
  labels:
    app: optimization-engine
    environment: {self.environment.value}
spec:
  replicas: 3
  selector:
    matchLabels:
      app: optimization-engine
  template:
    metadata:
      labels:
        app: optimization-engine
        version: v1.0.0
    spec:
      containers:
      - name: optimization-engine
        image: gcr.io/{self.config.project_id}/arcitek-optimization-engine:latest
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 9090
          name: metrics
        env:
        - name: ENVIRONMENT
          value: {self.environment.value}
        - name: LOG_LEVEL
          value: INFO
        - name: OPTIMIZATION_LEVEL
          value: ml_powered
        - name: AUTO_APPLY
          value: "false"
        - name: MONITORING_INTERVAL
          value: "60"
        envFrom:
        - configMapRef:
            name: arcitek-config
        - secretRef:
            name: arcitek-secrets
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: data
          mountPath: /data
        - name: logs
          mountPath: /logs
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: optimization-engine-data
      - name: logs
        emptyDir: {{}}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: optimization-engine-data
  namespace: arcitek-{self.environment.value}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: standard-rwo
"""
    
    def _create_monitoring_agent_manifest(self) -> str:
        """Create Kubernetes DaemonSet for monitoring agents"""
        return f"""apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: monitoring-agent
  namespace: arcitek-{self.environment.value}
  labels:
    app: monitoring-agent
    environment: {self.environment.value}
spec:
  selector:
    matchLabels:
      app: monitoring-agent
  template:
    metadata:
      labels:
        app: monitoring-agent
    spec:
      hostNetwork: true
      hostPID: true
      containers:
      - name: monitoring-agent
        image: gcr.io/{self.config.project_id}/arcitek-monitoring-agent:latest
        securityContext:
          privileged: true
        env:
        - name: ENGINE_ENDPOINT
          value: "http://optimization-engine:8080"
        - name: SECURITY_LEVEL
          value: "sha512"
        - name: MONITORING_INTERVAL
          value: "30"
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        envFrom:
        - secretRef:
            name: arcitek-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
        volumeMounts:
        - name: proc
          mountPath: /host/proc
          readOnly: true
        - name: sys
          mountPath: /host/sys
          readOnly: true
      volumes:
      - name: proc
        hostPath:
          path: /proc
      - name: sys
        hostPath:
          path: /sys
"""
    
    def _create_benchmark_manifest(self) -> str:
        """Create Kubernetes deployment for benchmark system"""
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: benchmark-system
  namespace: arcitek-{self.environment.value}
  labels:
    app: benchmark-system
    environment: {self.environment.value}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: benchmark-system
  template:
    metadata:
      labels:
        app: benchmark-system
    spec:
      containers:
      - name: benchmark-system
        image: gcr.io/{self.config.project_id}/arcitek-benchmark-system:latest
        ports:
        - containerPort: 8081
          name: http
        env:
        - name: TARGET_PERCENTILE
          value: "90"
        - name: BENCHMARK_INTERVAL
          value: "3600"
        envFrom:
        - configMapRef:
            name: arcitek-config
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        volumeMounts:
        - name: results
          mountPath: /results
      volumes:
      - name: results
        persistentVolumeClaim:
          claimName: benchmark-results
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: benchmark-results
  namespace: arcitek-{self.environment.value}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: standard-rwo
"""
    
    def _create_api_gateway_manifest(self) -> str:
        """Create Kubernetes deployment for API gateway"""
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: arcitek-{self.environment.value}
  labels:
    app: api-gateway
    environment: {self.environment.value}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: gcr.io/{self.config.project_id}/arcitek-api-gateway:latest
        ports:
        - containerPort: 80
          name: http
        - containerPort: 443
          name: https
        env:
        - name: OPTIMIZATION_ENGINE_URL
          value: "http://optimization-engine:8080"
        - name: BENCHMARK_SYSTEM_URL
          value: "http://benchmark-system:8081"
        envFrom:
        - configMapRef:
            name: arcitek-config
        - secretRef:
            name: arcitek-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 80
          initialDelaySeconds: 15
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
"""
    
    def _create_service_manifest(self, service_type: ServiceType) -> str:
        """Create Kubernetes service manifest"""
        service_config = {
            ServiceType.OPTIMIZATION_ENGINE: {
                'port': 8080,
                'target_port': 8080,
                'name': 'optimization-engine'
            },
            ServiceType.BENCHMARK_SYSTEM: {
                'port': 8081,
                'target_port': 8081,
                'name': 'benchmark-system'
            },
            ServiceType.API_GATEWAY: {
                'port': 80,
                'target_port': 80,
                'name': 'api-gateway'
            }
        }
        
        config = service_config.get(service_type)
        if not config:
            return ""
        
        return f"""apiVersion: v1
kind: Service
metadata:
  name: {config['name']}
  namespace: arcitek-{self.environment.value}
  labels:
    app: {config['name']}
spec:
  type: ClusterIP
  ports:
  - port: {config['port']}
    targetPort: {config['target_port']}
    protocol: TCP
    name: http
  selector:
    app: {config['name']}
"""
    
    def _create_ingress_manifest(self) -> str:
        """Create Kubernetes ingress for external access"""
        return f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: arcitek-ingress
  namespace: arcitek-{self.environment.value}
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: "arcitek-{self.environment.value}-ip"
    networking.gke.io/managed-certificates: "arcitek-cert"
    kubernetes.io/ingress.allow-http: "false"
spec:
  rules:
  - host: arcitek-{self.environment.value}.infinite2025.com
    http:
      paths:
      - path: /api/*
        pathType: ImplementationSpecific
        backend:
          service:
            name: api-gateway
            port:
              number: 80
      - path: /*
        pathType: ImplementationSpecific
        backend:
          service:
            name: api-gateway
            port:
              number: 80
---
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: arcitek-cert
  namespace: arcitek-{self.environment.value}
spec:
  domains:
    - arcitek-{self.environment.value}.infinite2025.com
"""
    
    def _create_configmap(self) -> str:
        """Create ConfigMap for configuration"""
        return f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: arcitek-config
  namespace: arcitek-{self.environment.value}
data:
  environment: {self.environment.value}
  project_id: {self.config.project_id}
  region: {self.config.region}
  log_level: INFO
  optimization_interval: "60"
  monitoring_interval: "30"
  benchmark_interval: "3600"
  target_percentile: "90"
  cache_hit_rate_min: "0.8"
  latency_max_ms: "100"
  memory_usage_max_mb: "1024"
"""
    
    def _create_secrets(self) -> str:
        """Create Secrets manifest template"""
        return f"""apiVersion: v1
kind: Secret
metadata:
  name: arcitek-secrets
  namespace: arcitek-{self.environment.value}
type: Opaque
stringData:
  shared_secret: "REPLACE_WITH_ACTUAL_SECRET"
  api_key: "REPLACE_WITH_API_KEY"
  db_password: "REPLACE_WITH_DB_PASSWORD"
  # Note: Replace these with actual secrets before deploying
"""
    
    def _create_hpa_manifest(self) -> str:
        """Create Horizontal Pod Autoscaler"""
        return f"""apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: optimization-engine-hpa
  namespace: arcitek-{self.environment.value}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: optimization-engine
  minReplicas: {self.config.min_nodes}
  maxReplicas: {self.config.max_nodes}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: arcitek-{self.environment.value}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
"""
    
    def generate_terraform_config(self) -> str:
        """Generate Terraform configuration for GCP infrastructure"""
        return f"""# ArciTEK.AI Google Cloud Infrastructure
# Terraform Configuration

terraform {{
  required_version = ">= 1.0"
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = "~> 5.0"
    }}
  }}
}}

provider "google" {{
  project = "{self.config.project_id}"
  region  = "{self.config.region}"
}}

# GKE Cluster
resource "google_container_cluster" "arcitek_cluster" {{
  name     = "{self.config.cluster_name}"
  location = "{self.config.zone}"

  # We can't create a cluster with no node pool defined, but we want to only use
  # separately managed node pools. So we create the smallest possible default
  # node pool and immediately delete it.
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  workload_identity_config {{
    workload_pool = "{self.config.project_id}.svc.id.goog"
  }}

  addons_config {{
    http_load_balancing {{
      disabled = false
    }}
    horizontal_pod_autoscaling {{
      disabled = false
    }}
  }}
}}

# Separately Managed Node Pool
resource "google_container_node_pool" "primary_nodes" {{
  name       = "primary-node-pool"
  location   = "{self.config.zone}"
  cluster    = google_container_cluster.arcitek_cluster.name
  node_count = {self.config.node_count}

  autoscaling {{
    min_node_count = {self.config.min_nodes}
    max_node_count = {self.config.max_nodes}
  }}

  node_config {{
    preemptible  = {str(self.environment != DeploymentEnvironment.PRODUCTION).lower()}
    machine_type = "{self.config.machine_type}"

    disk_size_gb = {self.config.disk_size_gb}
    disk_type    = "pd-standard"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    labels = {{
      environment = "{self.environment.value}"
      app         = "arcitek-ai"
    }}

    tags = ["arcitek", "{self.environment.value}"]
  }}
}}

# VPC Network
resource "google_compute_network" "vpc" {{
  name                    = "arcitek-vpc-{self.environment.value}"
  auto_create_subnetworks = false
}}

# Subnet
resource "google_compute_subnetwork" "subnet" {{
  name          = "arcitek-subnet-{self.environment.value}"
  ip_cidr_range = "10.10.0.0/24"
  region        = "{self.config.region}"
  network       = google_compute_network.vpc.name

  secondary_ip_range {{
    range_name    = "services-range"
    ip_cidr_range = "10.11.0.0/24"
  }}

  secondary_ip_range {{
    range_name    = "pod-ranges"
    ip_cidr_range = "10.12.0.0/16"
  }}
}}

# Cloud SQL Instance for PostgreSQL
resource "google_sql_database_instance" "postgres" {{
  name             = "arcitek-db-{self.environment.value}"
  database_version = "POSTGRES_15"
  region           = "{self.config.region}"

  settings {{
    tier = "db-f1-micro"
    
    backup_configuration {{
      enabled = true
      start_time = "03:00"
    }}

    ip_configuration {{
      ipv4_enabled = false
      private_network = google_compute_network.vpc.id
    }}
  }}
}}

# Cloud Storage Bucket for artifacts
resource "google_storage_bucket" "artifacts" {{
  name     = "arcitek-artifacts-{self.environment.value}"
  location = "{self.config.region}"

  uniform_bucket_level_access = true

  lifecycle_rule {{
    condition {{
      age = 30
    }}
    action {{
      type = "Delete"
    }}
  }}
}}

# Cloud Pub/Sub Topic for events
resource "google_pubsub_topic" "events" {{
  name = "arcitek-events-{self.environment.value}"
}}

# Cloud Pub/Sub Subscription
resource "google_pubsub_subscription" "events_sub" {{
  name  = "arcitek-events-sub-{self.environment.value}"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 20
}}

# Static IP for Ingress
resource "google_compute_global_address" "default" {{
  name = "arcitek-{self.environment.value}-ip"
}}

# Outputs
output "cluster_name" {{
  value = google_container_cluster.arcitek_cluster.name
}}

output "cluster_endpoint" {{
  value = google_container_cluster.arcitek_cluster.endpoint
}}

output "static_ip" {{
  value = google_compute_global_address.default.address
}}

output "bucket_name" {{
  value = google_storage_bucket.artifacts.name
}}
"""
    
    def generate_deployment_script(self) -> str:
        """Generate deployment script"""
        return f"""#!/bin/bash
# ArciTEK.AI GCP Deployment Script
# Environment: {self.environment.value}

set -e

echo "🚀 Deploying ArciTEK.AI to Google Cloud Platform"
echo "Environment: {self.environment.value}"
echo "Project: {self.config.project_id}"
echo "Region: {self.config.region}"

# Colors
GREEN='\\033[0;32m'
BLUE='\\033[0;34m'
RED='\\033[0;31m'
NC='\\033[0m'

# Set project
echo -e "${{BLUE}}Setting GCP project...${{NC}}"
gcloud config set project {self.config.project_id}

# Enable required APIs
echo -e "${{BLUE}}Enabling required GCP APIs...${{NC}}"
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable pubsub.googleapis.com

# Create namespace
echo -e "${{BLUE}}Creating Kubernetes namespace...${{NC}}"
kubectl create namespace arcitek-{self.environment.value} --dry-run=client -o yaml | kubectl apply -f -

# Apply Kubernetes manifests
echo -e "${{BLUE}}Deploying Kubernetes resources...${{NC}}"
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/optimization-engine-deployment.yaml
kubectl apply -f k8s/optimization-engine-service.yaml
kubectl apply -f k8s/monitoring-agent-daemonset.yaml
kubectl apply -f k8s/benchmark-system-deployment.yaml
kubectl apply -f k8s/benchmark-system-service.yaml
kubectl apply -f k8s/api-gateway-deployment.yaml
kubectl apply -f k8s/api-gateway-service.yaml
kubectl apply -f k8s/api-gateway-ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Wait for deployments
echo -e "${{BLUE}}Waiting for deployments to be ready...${{NC}}"
kubectl wait --for=condition=available --timeout=300s \\
  deployment/optimization-engine \\
  deployment/api-gateway \\
  deployment/benchmark-system \\
  -n arcitek-{self.environment.value}

# Get external IP
echo -e "${{BLUE}}Getting external IP address...${{NC}}"
kubectl get ingress arcitek-ingress -n arcitek-{self.environment.value}

echo -e "${{GREEN}}✅ Deployment completed successfully!${{NC}}"
echo ""
echo "Access your deployment at: https://arcitek-{self.environment.value}.infinite2025.com"
echo ""
echo "To check status:"
echo "  kubectl get pods -n arcitek-{self.environment.value}"
echo "  kubectl get services -n arcitek-{self.environment.value}"
echo "  kubectl get ingress -n arcitek-{self.environment.value}"
"""
    
    def save_manifests(self, output_dir: str = "./gcp-deployment") -> bool:
        """Save all manifests to files"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(f"{output_dir}/k8s", exist_ok=True)
            os.makedirs(f"{output_dir}/terraform", exist_ok=True)
            
            # Save Kubernetes manifests
            manifests = self.generate_kubernetes_manifests()
            for filename, content in manifests.items():
                filepath = f"{output_dir}/k8s/{filename}"
                with open(filepath, 'w') as f:
                    f.write(content)
                logger.info(f"Created {filepath}")
            
            # Save Terraform configuration
            terraform_config = self.generate_terraform_config()
            terraform_path = f"{output_dir}/terraform/main.tf"
            with open(terraform_path, 'w') as f:
                f.write(terraform_config)
            logger.info(f"Created {terraform_path}")
            
            # Save deployment script
            deploy_script = self.generate_deployment_script()
            script_path = f"{output_dir}/deploy.sh"
            with open(script_path, 'w') as f:
                f.write(deploy_script)
            os.chmod(script_path, 0o755)
            logger.info(f"Created {script_path}")
            
            # Create README
            readme = self._generate_readme()
            readme_path = f"{output_dir}/README.md"
            with open(readme_path, 'w') as f:
                f.write(readme)
            logger.info(f"Created {readme_path}")
            
            logger.info(f"All deployment files saved to {output_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save manifests: {e}")
            return False
    
    def _generate_readme(self) -> str:
        """Generate README for deployment"""
        return f"""# ArciTEK.AI Google Cloud Deployment

## Environment: {self.environment.value}

This directory contains all the necessary files to deploy ArciTEK.AI on Google Cloud Platform.

## Prerequisites

- Google Cloud SDK installed and configured
- kubectl installed
- Terraform installed (for infrastructure provisioning)
- Access to GCP project: {self.config.project_id}

## Deployment Steps

### 1. Infrastructure Provisioning (Terraform)

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 2. Configure kubectl

```bash
gcloud container clusters get-credentials {self.config.cluster_name} \\
  --zone {self.config.zone} \\
  --project {self.config.project_id}
```

### 3. Update Secrets

Edit `k8s/secrets.yaml` and replace placeholder values with actual secrets:
- shared_secret
- api_key
- db_password

### 4. Deploy Application

```bash
./deploy.sh
```

## Architecture

- **Optimization Engine**: 3 replicas with HPA (3-10 pods)
- **API Gateway**: 2 replicas with HPA (2-10 pods)
- **Monitoring Agents**: DaemonSet (1 per node)
- **Benchmark System**: 1 replica

## Monitoring

Check deployment status:

```bash
kubectl get pods -n arcitek-{self.environment.value}
kubectl get services -n arcitek-{self.environment.value}
kubectl get ingress -n arcitek-{self.environment.value}
```

View logs:

```bash
kubectl logs -f deployment/optimization-engine -n arcitek-{self.environment.value}
kubectl logs -f deployment/api-gateway -n arcitek-{self.environment.value}
```

## Scaling

The deployment includes Horizontal Pod Autoscalers (HPA) that automatically scale based on:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)

Manual scaling:

```bash
kubectl scale deployment optimization-engine --replicas=5 -n arcitek-{self.environment.value}
```

## Accessing the Application

Once deployed, access the application at:
https://arcitek-{self.environment.value}.infinite2025.com

## Troubleshooting

1. Check pod status:
   ```bash
   kubectl describe pod <pod-name> -n arcitek-{self.environment.value}
   ```

2. Check events:
   ```bash
   kubectl get events -n arcitek-{self.environment.value} --sort-by='.lastTimestamp'
   ```

3. Access pod shell:
   ```bash
   kubectl exec -it <pod-name> -n arcitek-{self.environment.value} -- /bin/bash
   ```

## Clean Up

To remove all resources:

```bash
kubectl delete namespace arcitek-{self.environment.value}
cd terraform
terraform destroy
```

## Support

For issues or questions, contact: nato1000@infinite2025.com
"""


def main():
    """Example: Generate deployment configuration"""
    
    # Configuration
    config = GCPConfig(
        project_id="arcitek-ai-production",
        region="us-central1",
        zone="us-central1-a",
        cluster_name="arcitek-gke-cluster",
        node_count=3,
        machine_type="n1-standard-4",
        disk_size_gb=100,
        auto_scaling=True,
        min_nodes=3,
        max_nodes=10
    )
    
    # Create deployment manager
    deployment = GCPDeployment(config, DeploymentEnvironment.PRODUCTION)
    
    # Generate and save all manifests
    deployment.save_manifests("./gcp-deployment")
    
    logger.info("GCP deployment configuration generated successfully!")


if __name__ == "__main__":
    main()

# Kubernetes Deployment Guide

This directory contains Kubernetes configuration files to deploy the QR Photo Upload application with 10 replicas and round-robin load balancing.

## Prerequisites

1. Docker installed and running
2. Kubernetes cluster (Minikube, Docker Desktop, or cloud provider)
3. `kubectl` configured to communicate with your cluster
4. Docker image built and pushed to a container registry

## Building and Pushing the Docker Image

1. Build the Docker image:
   ```bash
   docker build -t your-username/qr-photo-upload:latest .
   ```

2. Push to a container registry (if not using local cluster):
   ```bash
   docker push your-username/qr-photo-upload:latest
   ```

## Deploying to Kubernetes

1. Apply the Persistent Volume Claims:
   ```bash
   kubectl apply -f persistent-volume.yaml
   ```

2. Deploy the application:
   ```bash
   kubectl apply -f deployment.yaml
   ```

3. Create the service:
   ```bash
   kubectl apply -f service.yaml
   ```

## Verifying the Deployment

1. Check the pods (should show 10 replicas):
   ```bash
   kubectl get pods
   ```

2. Check the service:
   ```bash
   kubectl get svc qr-photo-upload-service
   ```

3. Access the application:
   - If using Minikube:
     ```bash
     minikube service qr-photo-upload-service
     ```
   - If using cloud provider, use the external IP from `kubectl get svc`

## Load Balancing

The service is configured with `sessionAffinity: None`, which enables round-robin load balancing between the 10 replicas. Each request will be distributed to a different pod in sequence.

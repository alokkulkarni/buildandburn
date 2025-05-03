output "ingress_hostname" {
  description = "Hostname of the ingress controller's load balancer"
  value       = try(data.kubernetes_service.ingress_nginx.status.0.load_balancer.0.ingress.0.hostname, "")
}

output "ingress_ip" {
  description = "IP address of the ingress controller's load balancer"
  value       = try(data.kubernetes_service.ingress_nginx.status.0.load_balancer.0.ingress.0.ip, "")
}

output "ingress_namespace" {
  description = "Namespace where the ingress controller is deployed"
  value       = kubernetes_namespace.ingress_nginx.metadata[0].name
}

output "ingress_service_name" {
  description = "Service name of the ingress controller"
  value       = "${helm_release.ingress_nginx.name}-controller"
} 
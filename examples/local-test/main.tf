terraform {
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

# Simulates a web application EC2 instance
resource "null_resource" "web_server" {
  triggers = {
    instance_type = var.instance_type
    ami_id        = var.ami_id
    environment   = var.environment
  }
}

# Simulates a security group — SSH opened to the world (intentional finding for review)
resource "null_resource" "web_sg" {
  triggers = {
    name             = "${var.environment}-web-sg"
    ingress_ssh_cidr = "0.0.0.0/0"     # Changed from 10.0.0.0/8 — should be flagged
    ingress_http     = "0.0.0.0/0"
    ingress_https    = "0.0.0.0/0"
    egress           = "0.0.0.0/0"
  }
}

# Simulates an RDS database instance — type change may force replacement
resource "null_resource" "app_db" {
  triggers = {
    identifier        = "${var.environment}-app-db"
    instance_class    = var.db_instance_class   # Changed from db.t3.small
    engine            = "postgres"
    engine_version    = "15.3"
    publicly_accessible = "true"                # Newly added — should be flagged
    deletion_protection = "false"
  }
}

# Simulates an S3 bucket for app assets
resource "null_resource" "app_assets_bucket" {
  triggers = {
    bucket = "${var.environment}-app-assets"
    acl    = "public-read"   # Changed from private — should be flagged
  }
}

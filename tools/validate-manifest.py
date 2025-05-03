#!/usr/bin/env python3
"""
Validate a manifest file for the BuildAndBurn application.
This script performs checks to ensure the manifest is well-formed and contains
all required fields in the correct format.
"""

import sys
import yaml
import json
import re
import os
from pprint import pprint


def validate_name(manifest):
    """Validate that the manifest has a valid name."""
    if 'name' not in manifest:
        return False, "Missing required field: 'name'"
    
    name = manifest['name']
    if not isinstance(name, str):
        return False, "Field 'name' must be a string"
    
    if not re.match(r'^[a-z0-9][-a-z0-9]*$', name):
        return False, "Field 'name' must contain only lowercase letters, numbers, and hyphens, and must start with a letter or number"
    
    return True, None


def validate_version(manifest):
    """Validate that the manifest has a valid version."""
    if 'version' not in manifest:
        return False, "Missing required field: 'version'"
    
    version = manifest['version']
    if not isinstance(version, str):
        return False, "Field 'version' must be a string"
    
    if not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+$', version) and not re.match(r'^[0-9]+\.[0-9]+$', version):
        return False, "Field 'version' must be in format 'X.Y.Z' or 'X.Y'"
    
    return True, None


def validate_region(manifest):
    """Validate that the manifest has a valid AWS region."""
    if 'region' not in manifest:
        return False, "Missing required field: 'region'"
    
    region = manifest['region']
    if not isinstance(region, str):
        return False, "Field 'region' must be a string"
    
    # Simple regex for AWS regions - not exhaustive but catches common problems
    if not re.match(r'^[a-z]{2}-[a-z]+-[0-9]$', region):
        return False, "Field 'region' does not appear to be a valid AWS region (e.g., 'us-west-2')"
    
    return True, None


def validate_dependencies(manifest):
    """Validate that the manifest dependencies are properly formatted."""
    if 'dependencies' not in manifest:
        return True, None  # Dependencies are optional
    
    dependencies = manifest['dependencies']
    if not isinstance(dependencies, list):
        return False, "Field 'dependencies' must be a list"
    
    allowed_types = {'database', 'queue', 'redis', 'kafka'}
    
    for i, dep in enumerate(dependencies):
        if not isinstance(dep, dict):
            return False, f"Dependency at index {i} must be an object"
        
        if 'type' not in dep:
            return False, f"Dependency at index {i} is missing required field 'type'"
        
        if dep['type'] not in allowed_types:
            return False, f"Dependency at index {i} has invalid type '{dep['type']}'. Allowed types: {', '.join(allowed_types)}"
    
    return True, None


def validate_services(manifest):
    """Validate that the manifest services are properly formatted."""
    if 'services' not in manifest:
        return False, "Missing required field: 'services'"
    
    services = manifest['services']
    if not isinstance(services, list):
        return False, "Field 'services' must be a list"
    
    if len(services) == 0:
        return False, "At least one service must be defined"
    
    service_names = set()
    
    for i, service in enumerate(services):
        if not isinstance(service, dict):
            return False, f"Service at index {i} must be an object"
        
        if 'name' not in service:
            return False, f"Service at index {i} is missing required field 'name'"
        
        name = service['name']
        if name in service_names:
            return False, f"Duplicate service name '{name}'"
        service_names.add(name)
        
        if 'image' not in service:
            return False, f"Service '{name}' is missing required field 'image'"
        
        if not isinstance(service.get('port', 0), int) and not service.get('port', '0').isdigit():
            return False, f"Service '{name}' field 'port' must be an integer"
    
    return True, None


def validate_ingress(manifest):
    """Validate that the manifest ingress configuration is properly formatted."""
    if 'ingress' not in manifest:
        return True, None  # Ingress is optional
    
    ingress = manifest['ingress']
    
    # Check for new format (hierarchical)
    if isinstance(ingress, dict):
        if 'enabled' in ingress and ingress['enabled'] is True:
            if 'hosts' not in ingress:
                return False, "When ingress is enabled, 'hosts' must be defined"
            
            hosts = ingress['hosts']
            if not isinstance(hosts, list):
                return False, "Ingress 'hosts' must be a list"
            
            for i, host in enumerate(hosts):
                if not isinstance(host, dict):
                    return False, f"Ingress host at index {i} must be an object"
                
                if 'host' not in host:
                    return False, f"Ingress host at index {i} is missing required field 'host'"
                
                if 'paths' not in host:
                    return False, f"Ingress host '{host['host']}' is missing required field 'paths'"
                
                paths = host['paths']
                if not isinstance(paths, list):
                    return False, f"Ingress host '{host['host']}' field 'paths' must be a list"
    
    # Check for old format (list of ingress rules)
    elif isinstance(ingress, list):
        for i, rule in enumerate(ingress):
            if not isinstance(rule, dict):
                return False, f"Ingress rule at index {i} must be an object"
            
            if 'service' not in rule:
                return False, f"Ingress rule at index {i} is missing required field 'service'"
            
            if 'port' not in rule:
                return False, f"Ingress rule at index {i} is missing required field 'port'"
    
    else:
        return False, "Field 'ingress' must be an object or a list"
    
    return True, None


def validate_manifest(manifest_path):
    """Validate a manifest file against expected schema."""
    try:
        with open(manifest_path, 'r') as f:
            manifest = yaml.safe_load(f)
    except Exception as e:
        return False, f"Failed to load manifest: {str(e)}"
    
    print(f"Validating manifest: {manifest_path}")
    
    # Required top-level fields
    required_validators = [
        validate_name,
        validate_version,
        validate_region,
        validate_services
    ]
    
    # Optional validators
    optional_validators = [
        validate_dependencies,
        validate_ingress
    ]
    
    # Run all validators
    validators = required_validators + optional_validators
    
    for validator in validators:
        success, error = validator(manifest)
        if not success:
            return False, error
    
    print("Manifest is valid!")
    return True, None


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate-manifest.py <manifest_file>")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    
    if not os.path.exists(manifest_path):
        print(f"Error: File not found: {manifest_path}")
        sys.exit(1)
    
    success, error = validate_manifest(manifest_path)
    
    if not success:
        print(f"Error: {error}")
        sys.exit(1)
    
    print("Validation successful!")


if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Script to automatically generate docs.json navigation file based on the contents
of the api-reference directory.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any


def get_group_name(service_dir: str) -> str:
    """
    Convert a service directory name to a proper group name for the navigation.
    
    Args:
        service_dir: The directory name (e.g., 'actions-service')
        
    Returns:
        Formatted group name (e.g., 'Actions Service')
    """
    # Handle special cases first
    service_names = {
        'api-keys-service': 'API Keys Service',
        'events-service': 'Events Service',
        'actions-service': 'Actions Service',
        'data-usage-service': 'Data Usage Service',
        'target-service': 'Target Service',
        'team-permissions-management-service': 'Team Permissions Management Service',
        'saml-configuration-service': 'SAML Configuration Service',
        'scopes-service': 'Scopes Service',
        'slos-service': 'Slos Service',
        'policies-service': 'Policies Service',
        'retentions-service': 'Retentions Service',
        'custom-enrichments-service': 'Custom Enrichments Service',
        'incidents-service': 'Incidents Service',
        'enrichments-service': 'Enrichments Service',
        'events2metrics-service': 'Events2Metrics Service',
        'rule-groups-service': 'Rule Groups Service',
        'entitiesservice': 'Entities Service',
        'integration-service': 'Integration Service',
        'testingservice': 'Testing Service',
        'globalroutersservice': 'Global Routers Service',
        'extension-testing-service': 'Extension Testing Service',
        'extension-service': 'Extension Service',
        'extension-deployment-service': 'Extension Deployment Service',
        'dashboard-service': 'Dashboard Service',
        'dashboard-folders-service': 'Dashboard Folders Service',
        'connectorsservice': 'Connectors Service',
        'presetsservice': 'Presets Service',
        'metricsconfiguratorpublicservice': 'Metrics Configurator Public Service',
        'metricstcoservice': 'Metrics Tco Service',
        'alert-definitions-service': 'Alert Definitions Service',
        'alert-events-service': 'Alert Events Service',
        'folders-for-views-service': 'Folders for Views',
        'views-service': 'Views',
        'outgoing-webhooks-service': 'Outgoing Webhooks Service',
        'recording-rules-service': 'Recording Rules Service',
        'contextual-data-integration-service': 'Contextual Data Integration Service'
    }
    
    return service_names[service_dir]
    
    


def get_mdx_files(service_path: Path) -> List[str]:
    """
    Get all .mdx files from a service directory and return their paths without extension.
    Overview page is always listed first, followed by other pages in alphabetical order.
    
    Args:
        service_path: Path to the service directory
        
    Returns:
        List of file paths without .mdx extension
    """
    mdx_files = []
    
    if service_path.is_dir():
        for file_path in service_path.iterdir():
            if file_path.is_file() and file_path.suffix == '.mdx':
                # Remove .mdx extension and convert to string
                file_name = file_path.stem
                mdx_files.append(file_name)
    
    # Sort all files alphabetically first
    mdx_files.sort()
    
    # Move overview to the front if it exists
    if 'overview' in mdx_files:
        mdx_files.remove('overview')
        mdx_files.insert(0, 'overview')
    
    return mdx_files


def build_navigation_structure(api_reference_path_latest: Path, api_reference_path_lts: Path) -> Dict[str, Any]:
    """
    Build the complete navigation structure for docs.json.
    
    Args:
        api_reference_path: Path to the api-reference directory
        
    Returns:
        Complete docs.json structure
    """
    # Base structure
    docs_structure = json.load(open("docs.json"))
    # docs_structure = {
    #     "$schema": "https://mintlify.com/docs.json",
    #     "theme": "mint",
    #     "name": "Coralogix Developer Docs",
    #     "colors": {
    #         "primary": "#16A34A",
    #         "light": "#07C983",
    #         "dark": "#15803D"
    #     },
    #     "favicon": "/favicon.svg",
    #     "navigation": {
    #         "versions": [
    #             {
    #                 "version": "1.5.2-latest", # This could be whatever, as the github action from the facade will override it anyways on release
    #                 "groups": [
    #                     {
    #                         "group": "Home",
    #                         "pages": [
    #                             "introduction"
    #                         ]
    #                     },
    #                     {
    #                         "group": "Use Cases",
    #                         "pages": [
    #                             "api-reference/introduction",
    #                             "api-reference/copy_a_dashboard",
    #                             "api-reference/create_an_alert_with_an_outgoing_webhook",
    #                             "api-reference/setup_kubernetes_complete_observability_integration",
    #                         ]
    #                     }
    #                 ]
    #             },
    #             {
    #                 "version": "1.5.2-lts", # This could be whatever, as the github action from the facade will override it anyways on release
    #                 "groups": [
    #                     {
    #                         "group": "Home",
    #                         "pages": [
    #                             "introduction"
    #                         ]
    #                     },
    #                     {
    #                         "group": "Use Cases",
    #                         "pages": [
    #                             "api-reference/introduction",
    #                             "api-reference/copy_a_dashboard",
    #                             "api-reference/create_an_alert_with_an_outgoing_webhook",
    #                             "api-reference/setup_kubernetes_complete_observability_integration",
    #                         ]
    #                     }
    #                 ]
    #             }
    #         ]
    #     },
    #     "logo": {
    #         "light": "/logo/coralogix.svg",
    #         "dark": "/logo/coralogix.svg"
    #     },
    #     "navbar": {
    #         "links": [
    #             {
    #                 "label": "Support",
    #                 "href": "mailto:hi@mintlify.com"
    #             }
    #         ]
    #     },
    #     "footer": {
    #         "socials": {
    #             "x": "https://twitter.com/Coralogix",
    #             "github": "https://github.com/coralogix",
    #             "linkedin": "https://linkedin.com/company/coralogix"
    #         }
    #     }
    # }
    # Get all directories in api-reference
    add_groups_to_navigation_structure(api_reference_path_latest, docs_structure, False)
    add_groups_to_navigation_structure(api_reference_path_lts, docs_structure, True)
    
    return docs_structure

def add_groups_to_navigation_structure(api_reference_path, docs_structure, is_lts):
    service_dirs = []
    for item in api_reference_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            service_dirs.append(item)
    
    # Sort directories for consistent ordering
    service_dirs.sort(key=lambda x: x.name.lower())
    
    # Build groups for each service
    groups = []
    for service_dir in service_dirs:
        service_name = service_dir.name
        mdx_files = get_mdx_files(service_dir)
        
        if mdx_files:  # Only add groups that have .mdx files
            group_name = get_group_name(service_name)
            
            # Create page paths
            subfolder = "lts" if is_lts else "latest"
            pages = [f"api-reference/{subfolder}/{service_name}/{file_name}" for file_name in mdx_files]
            
            group = {
                "group": group_name,
                "pages": pages
            }
            groups.append(group)
        docs_structure["navigation"]["versions"][is_lts]["groups"] = groups


def main():
    """
    Main function to generate the docs.json file.
    """
    # Get the current working directory
    current_dir = Path.cwd()
    api_reference_path_latest = current_dir / "api-reference" / "latest"
    api_reference_path_lts = current_dir / "api-reference" / "lts"
    
    
    print(f"Scanning {api_reference_path_latest} for service directories...")
    
    # Build the navigation structure
    docs_structure = build_navigation_structure(api_reference_path_latest, api_reference_path_lts)
    
    # Write to docs.json
    output_file = current_dir / "docs.json"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(docs_structure, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully generated {output_file}")
        print(f"Found {len(docs_structure['navigation']['versions'][0]['groups'])} service groups")
        
        # Print summary
        total_pages = sum(len(group['pages']) for group in docs_structure['navigation']['versions'][0]['groups'])
        print(f"Total pages: {total_pages}")
        
    except Exception as e:
        print(f"Error writing to {output_file}: {e}")


if __name__ == "__main__":
    main()
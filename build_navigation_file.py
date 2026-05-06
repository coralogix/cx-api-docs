#!/usr/bin/env python3
"""
Script to automatically generate docs.json navigation file based on the contents
of the api-reference directory for multiple API versions.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional


# Service mappings per version
# Maps directory name -> display name
# Only services that are enabled in configmap AND have handlers in main.go

V3_SERVICES = {
    'actions-service': 'Actions Service',
    'alert-definitions-service': 'Alert Definitions Service',
    'alert-events-service': 'Alert Events Service',
    'alert-scheduler-rule-service': 'Alert Scheduler Rule Service',
    'api-keys-service': 'API Keys Service',
    'connectors-service': 'Connectors Service',
    'contextual-data-integration-service': 'Contextual Data Integration Service',
    'custom-enrichments-service': 'Custom Enrichments Service',
    'dashboard-folders-service': 'Dashboard Folders Service',
    'dashboard-service': 'Dashboard Service',
    'data-usage-service': 'Data Usage Service',
    'enrichments-service': 'Enrichments Service',
    'entities-service': 'Entities Service',
    'events2metrics-service': 'Events2Metrics Service',
    'extension-deployment-service': 'Extension Deployment Service',
    'extension-service': 'Extension Service',
    'extension-testing-service': 'Extension Testing Service',
    'folders-for-views-service': 'Folders for Views Service',
    'global-routers-service': 'Global Routers Service',
    'incidents-service': 'Incidents Service',
    'integration-service': 'Integration Service',
    'ip-access-service': 'IP Access Service',
    'metrics-data-archive-service': 'Metrics Data Archive Service',
    'outgoing-webhooks-service': 'Outgoing Webhooks Service',
    'policies-service': 'Policies Service',
    'presets-service': 'Presets Service',
    'quota-allocation-rule-set-service': 'Quota Allocation Rule Set Service',
    'recording-rules-service': 'Recording Rules Service',
    'retentions-service': 'Retentions Service',
    'role-management-service': 'Role Management Service',
    'rule-groups-service': 'Rule Groups Service',
    'saml-configuration-service': 'SAML Configuration Service',
    'scopes-service': 'Scopes Service',
    'slos-service': 'SLOs Service',
    'target-service': 'Target Service',
    'team-config-service': 'Team Config Service',
    'views-service': 'Views Service',
}

V4_SERVICES = {
    **V3_SERVICES,
    'events-service': 'Events Service',
    'team-groups-management-service': 'Team Groups Management Service',
}

V5_SERVICES = {
    **V4_SERVICES,
}

VERSION_CONFIG = {
    'v5': {
        'display_name': 'v5',
        'services': V5_SERVICES,
        'intro_page': 'introduction-v5',
    },
    'v4': {
        'display_name': 'v4',
        'services': V4_SERVICES,
        'intro_page': 'introduction-v4',
    },
    'v3': {
        'display_name': 'v3',
        'services': V3_SERVICES,
        'intro_page': 'introduction-v3',
    },
}


def get_mdx_files(service_path: Path) -> List[str]:
    """Get all .mdx files from a service directory."""
    mdx_files = []
    
    if service_path.is_dir():
        for file_path in service_path.iterdir():
            if file_path.is_file() and file_path.suffix == '.mdx':
                mdx_files.append(file_path.stem)
    
    mdx_files.sort()
    
    if 'overview' in mdx_files:
        mdx_files.remove('overview')
        mdx_files.insert(0, 'overview')
    
    return mdx_files


def build_version_groups(api_ref_path: Path, version: str, config: dict) -> List[dict]:
    """Build navigation groups for a specific version."""
    version_path = api_ref_path / version
    if not version_path.exists():
        print(f"Warning: {version_path} does not exist")
        return []
    
    services = config['services']
    groups = []
    
    # Get all service directories
    service_dirs = sorted([d for d in version_path.iterdir() if d.is_dir()])
    
    for service_dir in service_dirs:
        service_name = service_dir.name
        
        if service_name not in services:
            continue
        
        mdx_files = get_mdx_files(service_dir)
        if not mdx_files:
            continue
        
        pages = [f"api-reference/{version}/{service_name}/{f}" for f in mdx_files]
        
        groups.append({
            "group": services[service_name],
            "pages": pages
        })
    
    # Add intro and use cases at the beginning
    intro_groups = [
        {
            "group": "Introduction",
            "pages": [config['intro_page']]
        },
        {
            "group": "Use Cases",
            "pages": [
                "copy_a_dashboard",
                "create_an_alert_with_an_outgoing_webhook",
                "setup_kubernetes_complete_observability_integration"
            ]
        }
    ]
    
    return intro_groups + groups


def build_navigation_structure(api_ref_path: Path) -> Dict[str, Any]:
    """Build the complete navigation structure for docs.json."""
    docs_structure = json.load(open("docs.json"))
    
    versions = []
    for version, config in VERSION_CONFIG.items():
        groups = build_version_groups(api_ref_path, version, config)
        if groups:
            versions.append({
                "version": config['display_name'],
                "groups": groups
            })
    
    docs_structure["navigation"]["versions"] = versions
    
    return docs_structure


def copy_overviews(current_dir: Path, api_ref_path: Path):
    """Copy service overview files to each version's service directories."""
    overviews_dir = current_dir / "service-overviews"
    if not overviews_dir.exists():
        print(f"Warning: {overviews_dir} does not exist, skipping overview copy")
        return
    
    for version in VERSION_CONFIG.keys():
        version_path = api_ref_path / version
        if not version_path.exists():
            continue
        
        for overview_file in overviews_dir.glob("*-overview.mdx"):
            service_name = overview_file.stem.replace("-overview", "")
            service_dir = version_path / service_name
            
            if service_dir.exists():
                dest = service_dir / "overview.mdx"
                shutil.copy(overview_file, dest)
                print(f"  Copied {overview_file.name} -> {version}/{service_name}/overview.mdx")


def main():
    current_dir = Path.cwd()
    api_ref_path = current_dir / "api-reference"
    
    print(f"Scanning {api_ref_path} for API versions...")
    
    print("Copying service overviews...")
    copy_overviews(current_dir, api_ref_path)
    
    docs_structure = build_navigation_structure(api_ref_path)
    
    output_file = current_dir / "docs.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(docs_structure, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully generated {output_file}")
    
    for version in docs_structure['navigation']['versions']:
        group_count = len(version['groups'])
        page_count = sum(len(g['pages']) for g in version['groups'])
        print(f"  {version['version']}: {group_count} groups, {page_count} pages")


if __name__ == "__main__":
    main()

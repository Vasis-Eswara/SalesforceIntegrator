"""
Bulk Data Insertion Utilities
Natural Language Processing and GitHub Config Support
"""
import re
import yaml
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class BulkDataParser:
    """Parse natural language prompts for bulk data creation"""
    
    def __init__(self):
        self.object_patterns = [
            r'create\s+(\d+)\s+(\w+)s?',  # "create 10 Accounts"
            r'(\d+)\s+(\w+)s?\s+(?:should|must|need)',  # "10 Accounts should"
            r'insert\s+(\d+)\s+(\w+)s?',  # "insert 5 Products"
            r'generate\s+(\d+)\s+(\w+)s?',  # "generate 3 Cases"
        ]
        
        self.relationship_patterns = [
            r'each\s+(\w+)\s+(?:should\s+)?(?:have|contain|include)\s+(\d+)\s+(\w+)s?',  # "each Account should have 3 Contacts"
            r'(\d+)\s+(\w+)s?\s+(?:for\s+)?each\s+(\w+)',  # "3 Contacts for each Account"
            r'link\s+(?:each\s+)?(\w+)\s+to\s+(?:a\s+)?(\w+)',  # "link each Opportunity to an Account"
            r'(\w+)s?\s+(?:should\s+)?belong\s+to\s+(\w+)s?',  # "Contacts should belong to Accounts"
        ]
    
    def parse_prompt(self, prompt: str) -> Dict[str, Any]:
        """Parse natural language prompt into structured data creation plan"""
        prompt = prompt.lower().strip()
        logger.info(f"Parsing prompt: {prompt}")
        
        result = {
            'objects': {},
            'relationships': [],
            'total_records': 0,
            'execution_order': [],
            'warnings': []
        }
        
        # Extract object creation instructions
        self._extract_objects(prompt, result)
        
        # Extract relationship instructions
        self._extract_relationships(prompt, result)
        
        # Calculate execution order based on relationships
        self._calculate_execution_order(result)
        
        # Calculate total records
        result['total_records'] = sum(obj['count'] for obj in result['objects'].values())
        
        logger.info(f"Parsed {len(result['objects'])} objects with {len(result['relationships'])} relationships")
        return result
    
    def _extract_objects(self, prompt: str, result: Dict[str, Any]):
        """Extract object creation instructions from prompt"""
        for pattern in self.object_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                count = int(match.group(1))
                object_name = self._normalize_object_name(match.group(2))
                
                if object_name in result['objects']:
                    # If object already exists, update count
                    result['objects'][object_name]['count'] += count
                else:
                    result['objects'][object_name] = {
                        'count': count,
                        'api_name': object_name,
                        'label': self._create_label(object_name),
                        'fields': {},
                        'children': []
                    }
                
                logger.debug(f"Found object: {object_name} (count: {count})")
    
    def _extract_relationships(self, prompt: str, result: Dict[str, Any]):
        """Extract relationship instructions from prompt"""
        for pattern in self.relationship_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                
                if len(groups) == 3 and groups[1].isdigit():
                    # Pattern: "each Account should have 3 Contacts"
                    parent = self._normalize_object_name(groups[0])
                    count = int(groups[1])
                    child = self._normalize_object_name(groups[2])
                    
                elif len(groups) == 3 and groups[0].isdigit():
                    # Pattern: "3 Contacts for each Account"
                    count = int(groups[0])
                    child = self._normalize_object_name(groups[1])
                    parent = self._normalize_object_name(groups[2])
                    
                elif len(groups) == 2:
                    # Pattern: "link Opportunity to Account"
                    child = self._normalize_object_name(groups[0])
                    parent = self._normalize_object_name(groups[1])
                    count = 1
                
                else:
                    continue
                
                relationship = {
                    'parent': parent,
                    'child': child,
                    'count': count,
                    'field_name': f"{parent}Id" if not parent.endswith('__c') else f"{parent[:-3]}__c"
                }
                
                result['relationships'].append(relationship)
                
                # Update child object count if it's a multiplier relationship
                if child in result['objects'] and parent in result['objects']:
                    if count > 1:
                        result['objects'][child]['count'] = result['objects'][parent]['count'] * count
                
                logger.debug(f"Found relationship: {parent} -> {child} (count: {count})")
    
    def _calculate_execution_order(self, result: Dict[str, Any]):
        """Calculate the order of object creation based on relationships"""
        objects = set(result['objects'].keys())
        ordered = []
        remaining = objects.copy()
        
        # Build dependency map
        dependencies = {}
        for obj in objects:
            dependencies[obj] = set()
        
        for rel in result['relationships']:
            if rel['child'] in dependencies:
                dependencies[rel['child']].add(rel['parent'])
        
        # Topological sort
        while remaining:
            # Find objects with no dependencies
            ready = [obj for obj in remaining if not dependencies[obj] or dependencies[obj].issubset(set(ordered))]
            
            if not ready:
                # Circular dependency or missing object - add remaining in alphabetical order
                ready = sorted(remaining)
                result['warnings'].append(f"Potential circular dependency detected. Objects will be created in alphabetical order: {', '.join(ready)}")
                ordered.extend(ready)
                break
            
            # Add ready objects to order
            for obj in ready:
                ordered.append(obj)
                remaining.remove(obj)
        
        result['execution_order'] = ordered
        logger.info(f"Execution order: {' -> '.join(ordered)}")
    
    def _normalize_object_name(self, name: str) -> str:
        """Normalize object name to proper Salesforce API format"""
        name = name.strip().title()
        
        # Handle common standard objects
        standard_objects = {
            'account': 'Account',
            'contact': 'Contact',
            'opportunity': 'Opportunity',
            'case': 'Case',
            'lead': 'Lead',
            'product': 'Product2',
            'user': 'User',
            'campaign': 'Campaign'
        }
        
        if name.lower() in standard_objects:
            return standard_objects[name.lower()]
        
        # For custom objects, ensure __c suffix
        if not name.endswith('__c') and name not in standard_objects.values():
            name = f"{name}__c"
        
        return name
    
    def _create_label(self, api_name: str) -> str:
        """Create a readable label from API name"""
        if api_name.endswith('__c'):
            label = api_name[:-3]
        else:
            label = api_name
        
        # Convert PascalCase to Title Case
        label = re.sub(r'([A-Z])', r' \1', label).strip()
        return label

class GitHubConfigParser:
    """Parse GitHub-hosted YAML configuration files"""
    
    def __init__(self):
        self.supported_formats = ['yaml', 'yml', 'json']
    
    def parse_github_url(self, github_url: str) -> Dict[str, Any]:
        """Parse GitHub URL and fetch configuration"""
        logger.info(f"Parsing GitHub URL: {github_url}")
        
        # Convert GitHub blob URL to raw URL
        raw_url = self._convert_to_raw_url(github_url)
        
        # Fetch file content
        content = self._fetch_file_content(raw_url)
        
        # Parse content based on file extension
        config = self._parse_content(content, raw_url)
        
        # Convert to standard format
        result = self._convert_to_standard_format(config)
        
        logger.info(f"Successfully parsed GitHub config with {len(result.get('objects', {}))} objects")
        return result
    
    def _convert_to_raw_url(self, github_url: str) -> str:
        """Convert GitHub blob URL to raw content URL"""
        if 'github.com' not in github_url:
            raise ValueError("URL must be from github.com")
        
        # Convert blob URL to raw URL
        if '/blob/' in github_url:
            raw_url = github_url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
        else:
            raw_url = github_url
        
        logger.debug(f"Converted to raw URL: {raw_url}")
        return raw_url
    
    def _fetch_file_content(self, url: str) -> str:
        """Fetch file content from URL"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch file from {url}: {str(e)}")
            raise Exception(f"Failed to fetch configuration file: {str(e)}")
    
    def _parse_content(self, content: str, url: str) -> Dict[str, Any]:
        """Parse content based on file type"""
        file_extension = url.split('.')[-1].lower()
        
        try:
            if file_extension in ['yaml', 'yml']:
                return yaml.safe_load(content)
            elif file_extension == 'json':
                return json.loads(content)
            else:
                # Try YAML first, then JSON
                try:
                    return yaml.safe_load(content)
                except yaml.YAMLError:
                    return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to parse content as {file_extension}: {str(e)}")
            raise Exception(f"Failed to parse configuration file: {str(e)}")
    
    def _convert_to_standard_format(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert various config formats to standard format"""
        result = {
            'objects': {},
            'relationships': [],
            'total_records': 0,
            'execution_order': [],
            'warnings': [],
            'source': 'github'
        }
        
        # Handle Snowfakery format
        if 'objects' in config or 'sobjects' in config:
            self._parse_snowfakery_format(config, result)
        
        # Handle custom format
        elif 'data' in config:
            self._parse_custom_format(config, result)
        
        # Handle direct object definition
        else:
            self._parse_direct_format(config, result)
        
        # Calculate execution order
        self._calculate_execution_order(result)
        
        # Calculate total records
        result['total_records'] = sum(obj['count'] for obj in result['objects'].values())
        
        return result
    
    def _parse_snowfakery_format(self, config: Dict[str, Any], result: Dict[str, Any]):
        """Parse Snowfakery recipe format"""
        objects_config = config.get('objects', config.get('sobjects', {}))
        
        for obj_name, obj_config in objects_config.items():
            count = obj_config.get('count', 1)
            
            result['objects'][obj_name] = {
                'count': count,
                'api_name': obj_name,
                'label': obj_config.get('label', obj_name),
                'fields': obj_config.get('fields', {}),
                'children': []
            }
        
        logger.debug(f"Parsed Snowfakery format with {len(result['objects'])} objects")
    
    def _parse_custom_format(self, config: Dict[str, Any], result: Dict[str, Any]):
        """Parse custom configuration format"""
        data_config = config['data']
        
        for item in data_config:
            obj_name = item['object']
            count = item.get('count', 1)
            
            result['objects'][obj_name] = {
                'count': count,
                'api_name': obj_name,
                'label': item.get('label', obj_name),
                'fields': item.get('fields', {}),
                'children': []
            }
        
        logger.debug(f"Parsed custom format with {len(result['objects'])} objects")
    
    def _parse_direct_format(self, config: Dict[str, Any], result: Dict[str, Any]):
        """Parse direct object definition format"""
        for obj_name, obj_config in config.items():
            if isinstance(obj_config, dict):
                count = obj_config.get('count', 1)
                
                result['objects'][obj_name] = {
                    'count': count,
                    'api_name': obj_name,
                    'label': obj_config.get('label', obj_name),
                    'fields': obj_config.get('fields', {}),
                    'children': []
                }
        
        logger.debug(f"Parsed direct format with {len(result['objects'])} objects")
    
    def _calculate_execution_order(self, result: Dict[str, Any]):
        """Calculate execution order for GitHub config"""
        # Simple alphabetical order for now - can be enhanced
        result['execution_order'] = sorted(result['objects'].keys())

def validate_data_plan(plan: Dict[str, Any], available_objects: List[str]) -> Dict[str, Any]:
    """Validate data creation plan against available Salesforce objects"""
    validation_result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'suggestions': []
    }
    
    # Check if objects exist in Salesforce
    available_objects_lower = [obj.lower() for obj in available_objects]
    
    for obj_name in plan['objects']:
        if obj_name.lower() not in available_objects_lower:
            validation_result['errors'].append(f"Object '{obj_name}' not found in Salesforce org")
            validation_result['valid'] = False
        else:
            # Find exact match for case sensitivity
            exact_match = next((obj for obj in available_objects if obj.lower() == obj_name.lower()), obj_name)
            if exact_match != obj_name:
                validation_result['warnings'].append(f"Object name case corrected: '{obj_name}' -> '{exact_match}'")
                # Update the plan with correct case
                plan['objects'][exact_match] = plan['objects'].pop(obj_name)
    
    # Validate record counts
    for obj_name, obj_config in plan['objects'].items():
        if obj_config['count'] > 200:
            validation_result['warnings'].append(f"Large record count for {obj_name}: {obj_config['count']}. Consider using Bulk API.")
        elif obj_config['count'] <= 0:
            validation_result['errors'].append(f"Invalid record count for {obj_name}: {obj_config['count']}")
            validation_result['valid'] = False
    
    return validation_result
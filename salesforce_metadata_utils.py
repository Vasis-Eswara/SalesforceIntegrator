"""
Salesforce Metadata API utilities for programmatic custom object creation
Implements CustomObject creation similar to Java Metadata API
"""
import logging
import requests
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class SalesforceMetadataClient:
    """
    Salesforce Metadata API client for creating custom objects and fields
    """
    
    def __init__(self, instance_url: str, access_token: str):
        """
        Initialize the Metadata API client
        
        Args:
            instance_url (str): Salesforce instance URL
            access_token (str): Valid Salesforce access token
        """
        self.instance_url = instance_url.rstrip('/')
        self.access_token = access_token
        self.api_version = "58.0"
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def create_custom_object(self, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a custom object using Metadata API
        
        Args:
            object_config (dict): Custom object configuration
            
        Returns:
            dict: Creation result
        """
        try:
            object_name = object_config.get('api_name', '').replace('__c', '')
            
            # Prepare custom object metadata for Tooling API
            custom_object_metadata = {
                "FullName": f"{object_name}__c",
                "Label": object_config.get('label', object_name),
                "PluralLabel": object_config.get('plural_label', f"{object_name}s"),
                "DeploymentStatus": "Deployed",
                "SharingModel": "ReadWrite",
                "NameField": {
                    "Label": "Name",
                    "Type": "Text"
                },
                "EnableActivities": True,
                "EnableBulkApi": True,
                "EnableReports": True,
                "EnableSearch": True,
                "EnableSharing": True,
                "EnableStreamingApi": True
            }
            
            # Add description if provided
            if object_config.get('description'):
                custom_object_metadata["Description"] = object_config['description']
            else:
                custom_object_metadata["Description"] = f"Custom object for {object_name.lower()} management"
            
            logger.info(f"Creating custom object: {object_name}__c")
            logger.debug(f"Metadata payload: {json.dumps(custom_object_metadata, indent=2)}")
            
            # Use Tooling API to create custom object
            url = f"{self.instance_url}/services/data/v{self.api_version}/tooling/sobjects/CustomObject"
            
            response = requests.post(
                url,
                headers=self.headers,
                json=custom_object_metadata,
                timeout=30
            )
            
            logger.info(f"Custom object creation response: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            
            if response.status_code == 201:
                result = response.json()
                return {
                    'success': True,
                    'id': result.get('id'),
                    'object_name': f"{object_name}__c",
                    'message': f"Successfully created custom object {object_name}__c"
                }
            else:
                error_details = response.text
                try:
                    error_json = response.json()
                    error_details = error_json.get('message', error_details)
                except:
                    pass
                
                return {
                    'success': False,
                    'error': f"Failed to create custom object: {error_details}",
                    'status_code': response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error creating custom object: {str(e)}")
            return {
                'success': False,
                'error': f"Exception during custom object creation: {str(e)}"
            }
    
    def create_custom_field(self, object_name: str, field_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a custom field on an object using Tooling API
        
        Args:
            object_name (str): Target object name
            field_config (dict): Field configuration
            
        Returns:
            dict: Creation result
        """
        try:
            field_name = field_config.get('api_name', '').replace('__c', '')
            
            # Prepare field metadata for Tooling API
            field_metadata = {
                "FullName": f"{object_name}.{field_name}__c",
                "Label": field_config.get('label', field_name),
                "Type": self._map_field_type(field_config.get('type', 'Text'))
            }
            
            # Add type-specific properties
            field_type = field_config.get('type', 'Text').lower()
            
            if field_type in ['text', 'string']:
                field_metadata["Length"] = field_config.get('length', 255)
            elif field_type in ['textarea', 'longtext']:
                field_metadata["Length"] = field_config.get('length', 32768)
                field_metadata["VisibleLines"] = field_config.get('visible_lines', 3)
            elif field_type in ['number', 'currency', 'percent']:
                field_metadata["Precision"] = field_config.get('precision', 18)
                field_metadata["Scale"] = field_config.get('scale', 0 if field_type == 'number' else 2)
            elif field_type == 'picklist':
                # Handle picklist values if provided
                values = field_config.get('picklist_values', ['Option 1', 'Option 2'])
                field_metadata["ValueSet"] = {
                    "ValueSetDefinition": {
                        "Value": [{"FullName": val, "Default": i == 0} for i, val in enumerate(values)]
                    }
                }
            
            # Add description and required flag
            if field_config.get('description'):
                field_metadata["Description"] = field_config['description']
            
            if field_config.get('required', False):
                field_metadata["Required"] = True
            
            logger.info(f"Creating custom field: {field_name}__c on {object_name}")
            logger.debug(f"Field metadata: {json.dumps(field_metadata, indent=2)}")
            
            # Use Tooling API to create custom field
            url = f"{self.instance_url}/services/data/v{self.api_version}/tooling/sobjects/CustomField"
            
            response = requests.post(
                url,
                headers=self.headers,
                json=field_metadata,
                timeout=30
            )
            
            logger.info(f"Field creation response: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            
            if response.status_code == 201:
                result = response.json()
                return {
                    'success': True,
                    'id': result.get('id'),
                    'field_name': f"{field_name}__c",
                    'object_name': object_name,
                    'message': f"Successfully created field {field_name}__c on {object_name}"
                }
            else:
                error_details = response.text
                try:
                    error_json = response.json()
                    error_details = error_json.get('message', error_details)
                except:
                    pass
                
                return {
                    'success': False,
                    'error': f"Failed to create field: {error_details}",
                    'status_code': response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error creating custom field: {str(e)}")
            return {
                'success': False,
                'error': f"Exception during field creation: {str(e)}"
            }
    
    def _map_field_type(self, field_type: str) -> str:
        """
        Map internal field types to Salesforce Metadata API types
        
        Args:
            field_type (str): Internal field type
            
        Returns:
            str: Salesforce Metadata API field type
        """
        type_mapping = {
            'text': 'Text',
            'string': 'Text',
            'textarea': 'LongTextArea',
            'longtext': 'LongTextArea',
            'number': 'Number',
            'currency': 'Currency',
            'percent': 'Percent',
            'date': 'Date',
            'datetime': 'DateTime',
            'checkbox': 'Checkbox',
            'email': 'Email',
            'phone': 'Phone',
            'url': 'Url',
            'picklist': 'Picklist',
            'multipicklist': 'MultiselectPicklist'
        }
        
        return type_mapping.get(field_type.lower(), 'Text')
    
    def check_object_exists(self, object_name: str) -> bool:
        """
        Check if a custom object already exists
        
        Args:
            object_name (str): Object name to check
            
        Returns:
            bool: True if object exists, False otherwise
        """
        try:
            url = f"{self.instance_url}/services/data/v{self.api_version}/sobjects/{object_name}/describe"
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def apply_configuration(self, configuration: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a complete configuration (objects and fields) to Salesforce
        
        Args:
            configuration (dict): Configuration from comprehensive_config_parser
            
        Returns:
            dict: Application results
        """
        results = {
            'success': True,
            'objects_created': [],
            'fields_created': [],
            'errors': []
        }
        
        try:
            actions = configuration.get('actions', [])
            
            # First pass: Create custom objects
            for action in actions:
                if action['type'] == 'create_object':
                    object_name = action['target']['object']
                    
                    # Check if object already exists
                    if self.check_object_exists(object_name):
                        logger.info(f"Object {object_name} already exists, skipping creation")
                        continue
                    
                    result = self.create_custom_object(action['details'])
                    
                    if result['success']:
                        results['objects_created'].append(result)
                        logger.info(f"Successfully created object: {object_name}")
                    else:
                        results['errors'].append(f"Object creation failed: {result['error']}")
                        results['success'] = False
            
            # Second pass: Create custom fields
            for action in actions:
                if action['type'] == 'create_field':
                    object_name = action['target']['object']
                    field_config = action['details']
                    
                    result = self.create_custom_field(object_name, field_config)
                    
                    if result['success']:
                        results['fields_created'].append(result)
                        logger.info(f"Successfully created field: {field_config['api_name']} on {object_name}")
                    else:
                        results['errors'].append(f"Field creation failed: {result['error']}")
                        # Don't mark as failed for field errors, as objects may still be created
            
            return results
            
        except Exception as e:
            logger.error(f"Error applying configuration: {str(e)}")
            return {
                'success': False,
                'error': f"Configuration application failed: {str(e)}",
                'objects_created': results.get('objects_created', []),
                'fields_created': results.get('fields_created', []),
                'errors': results.get('errors', [])
            }


def create_metadata_client(instance_url: str, access_token: str) -> SalesforceMetadataClient:
    """
    Factory function to create a Salesforce Metadata API client
    
    Args:
        instance_url (str): Salesforce instance URL
        access_token (str): Valid Salesforce access token
        
    Returns:
        SalesforceMetadataClient: Configured client instance
    """
    return SalesforceMetadataClient(instance_url, access_token)
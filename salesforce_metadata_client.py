"""
Salesforce Metadata API client for programmatic custom object creation
Implements the CORRECT approach using SOAP-based Metadata API with zeep
"""
import logging
import requests
import json
import re
from typing import Dict, List, Any, Optional
try:
    from zeep import Client
    from zeep.transports import Transport
    from requests import Session
    ZEEP_AVAILABLE = True
except ImportError:
    ZEEP_AVAILABLE = False
    Client = None
    Transport = None
    Session = None

logger = logging.getLogger(__name__)


class SalesforceMetadataClient:
    """
    Salesforce Metadata API client for creating custom objects and fields
    Uses the proper Metadata API REST endpoints with correct JSON structure
    """
    
    def __init__(self, instance_url: str, access_token: str, salesforce_connection=None):
        """
        Initialize the Metadata API client
        
        Args:
            instance_url (str): Salesforce instance URL
            access_token (str): Valid Salesforce access token
            salesforce_connection: Optional Salesforce connection object
        """
        self.instance_url = instance_url.rstrip('/')
        self.access_token = access_token
        self.api_version = "58.0"
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        self.sf_connection = salesforce_connection
        
        # Initialize SOAP client for Metadata API
        self.soap_client = None
        self._initialize_soap_client()
    
    def _normalize_object_name(self, name: str) -> str:
        """
        Convert sentence format object names to proper API names
        
        Examples:
        - "Project Tracker" -> "Project_Tracker"
        - "project tracker" -> "Project_Tracker"
        - "ProjectTracker" -> "Project_Tracker"
        - "Invoice Management System" -> "Invoice_Management_System"
        
        Args:
            name (str): Original object name
            
        Returns:
            str: Normalized API name
        """
        # Remove any existing __c suffix
        name = name.replace('__c', '')
        
        # Split on spaces and common separators
        words = re.split(r'[_\s-]+', name.strip())
        
        # Handle camelCase by splitting on capital letters
        expanded_words = []
        for word in words:
            if word:
                # Split camelCase words
                camel_parts = re.findall(r'[A-Z][a-z]*|[a-z]+', word)
                expanded_words.extend(camel_parts)
        
        # Capitalize each word and join with underscores
        api_name = '_'.join(word.capitalize() for word in expanded_words if word)
        
        return api_name
    
    def _create_label_from_name(self, name: str) -> str:
        """
        Create a proper label from the original name
        
        Args:
            name (str): Original object name
            
        Returns:
            str: Proper label
        """
        # Remove __c suffix
        name = name.replace('__c', '')
        
        # Split on underscores, spaces, and handle camelCase
        words = re.split(r'[_\s-]+', name.strip())
        expanded_words = []
        
        for word in words:
            if word:
                # Split camelCase words
                camel_parts = re.findall(r'[A-Z][a-z]*|[a-z]+', word)
                expanded_words.extend(camel_parts)
        
        # Capitalize each word and join with spaces
        label = ' '.join(word.capitalize() for word in expanded_words if word)
        
        return label
    
    def _create_plural_label_from_name(self, name: str) -> str:
        """
        Create a proper plural label from the original name
        
        Args:
            name (str): Original object name
            
        Returns:
            str: Proper plural label
        """
        label = self._create_label_from_name(name)
        
        # Simple pluralization rules
        if label.endswith('y') and not label.endswith('ay'):
            return label[:-1] + 'ies'
        elif label.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return label + 'es'
        elif label.endswith('on'):
            return label[:-2] + 'ons'
        else:
            return label + 's'
    
    def _initialize_soap_client(self):
        """
        Initialize the SOAP client for Metadata API using zeep
        """
        if not ZEEP_AVAILABLE:
            logger.warning("zeep library not available - SOAP client disabled")
            self.soap_client = None
            return
            
        try:
            # Metadata API WSDL URL
            metadata_wsdl_url = f"{self.instance_url}/services/wsdl/metadata/{self.api_version}"
            
            # Create session with authentication
            session = Session()
            session.headers.update({
                'Authorization': f'Bearer {self.access_token}',
                'SOAPAction': 'urn:create'
            })
            
            # Create transport and client
            transport = Transport(session=session)
            self.soap_client = Client(metadata_wsdl_url, transport=transport)
            
            logger.info("✓ Successfully initialized zeep SOAP Metadata API client")
            
        except Exception as e:
            logger.error(f"Failed to initialize zeep SOAP client: {str(e)}")
            self.soap_client = None
    
    def create_custom_object(self, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a custom object using Metadata API
        
        Args:
            object_config (dict): Custom object configuration
            
        Returns:
            dict: Creation result
        """
        try:
            # Handle sentence-format object names properly
            original_name = object_config.get('api_name', '').replace('__c', '')
            
            # Convert sentence format to proper API name
            api_name = self._normalize_object_name(original_name)
            
            # Create proper labels from the original name
            label = self._create_label_from_name(original_name)
            plural_label = self._create_plural_label_from_name(original_name)
            
            # Prepare custom object metadata for Metadata API
            custom_object_metadata = {
                "Metadata": {
                    "fullName": f"{api_name}__c",
                    "label": label,
                    "pluralLabel": plural_label,
                    "nameField": {
                        "type": "Text",
                        "label": "Name"
                    },
                    "deploymentStatus": "Deployed",
                    "sharingModel": "ReadWrite",
                    "enableActivities": True,
                    "enableReports": True,
                    "enableSearch": True,
                    "enableHistory": False,
                    "enableFeeds": False,
                    "enableBulkApi": True,
                    "enableStreamingApi": True
                }
            }
            
            # Add description
            if object_config.get('description'):
                custom_object_metadata["Metadata"]["description"] = object_config['description']
            else:
                custom_object_metadata["Metadata"]["description"] = f"Custom object for {label.lower()} management"
            
            logger.info(f"Creating custom object: {api_name}__c (Label: {label})")
            logger.debug(f"Metadata payload: {json.dumps(custom_object_metadata, indent=2)}")
            
            # Use SOAP-based Metadata API through zeep
            if self.soap_client:
                try:
                    logger.info(f"Attempting zeep SOAP Metadata API object creation for {api_name}__c")
                    
                    # Create custom object metadata for SOAP API using zeep structure
                    custom_object = {
                        'fullName': f"{api_name}__c",
                        'label': label,
                        'pluralLabel': plural_label,
                        'nameField': {
                            'type': 'Text',
                            'label': 'Name'
                        },
                        'deploymentStatus': 'Deployed',
                        'sharingModel': 'ReadWrite',
                        'enableActivities': True,
                        'enableReports': True,
                        'enableSearch': True,
                        'enableHistory': False,
                        'enableFeeds': False,
                        'enableBulkApi': True,
                        'enableStreamingApi': True,
                        'description': custom_object_metadata["Metadata"]["description"]
                    }
                    
                    logger.debug(f"zeep SOAP metadata payload: {json.dumps(custom_object, indent=2)}")
                    
                    # Create the custom object using zeep client
                    result = self.soap_client.service.create([custom_object])
                    logger.info(f"zeep SOAP API call completed, result: {result}")
                    
                    if result and len(result) > 0 and hasattr(result[0], 'success') and result[0].success:
                        logger.info(f"✓ Successfully created custom object via zeep SOAP: {api_name}__c")
                        return {
                            'success': True,
                            'id': getattr(result[0], 'id', 'unknown'),
                            'object_name': f"{api_name}__c",
                            'object_label': label,
                            'message': f"Successfully created custom object '{label}' ({api_name}__c) via zeep SOAP Metadata API"
                        }
                    else:
                        error_msg = []
                        if result and len(result) > 0:
                            if hasattr(result[0], 'errors') and result[0].errors:
                                error_msg = [err.message for err in result[0].errors]
                            else:
                                error_msg = ['zeep SOAP creation failed - no specific error']
                        else:
                            error_msg = ['zeep SOAP - no result returned']
                        
                        logger.error(f"zeep SOAP object creation failed: {error_msg}")
                        return {
                            'success': False,
                            'error': f"zeep SOAP Metadata API failed: {'; '.join(error_msg)}",
                            'object_name': f"{api_name}__c",
                            'object_label': label
                        }
                except Exception as e:
                    logger.error(f"zeep SOAP Metadata API exception: {str(e)}")
                    # Try direct Tooling API approach as fallback
                    return self._try_tooling_api_object_creation(api_name, label, plural_label, object_config)
            else:
                logger.warning("No zeep SOAP client available, trying Tooling API")
                # Try direct Tooling API approach
                return self._try_tooling_api_object_creation(api_name, label, plural_label, object_config)
                
        except Exception as e:
            logger.error(f"Error creating custom object: {str(e)}")
            return {
                'success': False,
                'error': f"Exception during custom object creation: {str(e)}"
            }
    
    def _try_tooling_api_object_creation(self, api_name: str, label: str, plural_label: str, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Try creating custom object via Tooling API as fallback
        """
        try:
            logger.info(f"Attempting Tooling API object creation for {api_name}__c")
            
            # Prepare custom object metadata for Tooling API
            custom_object_metadata = {
                "FullName": f"{api_name}__c",
                "MasterLabel": label,
                "PluralLabel": plural_label,
                "NameField": {
                    "Type": "Text",
                    "Label": "Name"
                },
                "DeploymentStatus": "Deployed",
                "SharingModel": "ReadWrite"
            }
            
            logger.debug(f"Tooling API payload: {json.dumps(custom_object_metadata, indent=2)}")
            
            # Use Tooling API to create custom object
            url = f"{self.instance_url}/services/data/v{self.api_version}/tooling/sobjects/CustomObject"
            
            response = requests.post(
                url,
                headers=self.headers,
                json=custom_object_metadata,
                timeout=30
            )
            
            logger.info(f"Tooling API response: {response.status_code}")
            logger.debug(f"Tooling API response body: {response.text}")
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"✓ Successfully created custom object via Tooling API: {api_name}__c")
                return {
                    'success': True,
                    'id': result.get('id'),
                    'object_name': f"{api_name}__c",
                    'object_label': label,
                    'message': f"Successfully created custom object '{label}' ({api_name}__c) via Tooling API"
                }
            else:
                error_details = response.text
                try:
                    error_json = response.json()
                    if isinstance(error_json, list) and len(error_json) > 0:
                        error_details = error_json[0].get('message', error_details)
                except:
                    pass
                
                logger.error(f"Tooling API failed: {error_details}")
                return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
                
        except Exception as e:
            logger.error(f"Tooling API exception: {str(e)}")
            return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)

    def _create_object_via_manual_fallback(self, api_name: str, label: str, plural_label: str, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback approach with manual creation instructions
        """
        try:
            return {
                'success': False,
                'error': f"Custom object creation requires manual setup. Please create object '{label}' ({api_name}__c) manually in Salesforce Setup, then fields will be created automatically.",
                'object_name': f"{api_name}__c",
                'object_label': label,
                'manual_creation_needed': True,
                'instructions': [
                    f"1. Go to Setup → Object Manager → Create → Custom Object",
                    f"2. Set Object Label: {label}",
                    f"3. Set Plural Label: {plural_label}",
                    f"4. Set Object Name: {api_name}",
                    f"5. Enable desired features and save",
                    f"6. Return here and create fields automatically"
                ]
            }
        except Exception as e:
            logger.error(f"Error in fallback: {str(e)}")
            return {
                'success': False,
                'error': f"Failed to create custom object: {str(e)}"
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
                "Metadata": {
                    "fullName": f"{object_name}.{field_name}__c",
                    "label": field_config.get('label', field_name),
                    "type": self._map_field_type(field_config.get('type', 'Text'))
                }
            }
            
            # Add type-specific properties
            field_type = field_config.get('type', 'Text').lower()
            
            if field_type in ['text', 'string']:
                field_metadata["Metadata"]["length"] = field_config.get('length', 255)
            elif field_type in ['textarea', 'longtext']:
                field_metadata["Metadata"]["length"] = field_config.get('length', 32768)
                field_metadata["Metadata"]["visibleLines"] = field_config.get('visible_lines', 3)
            elif field_type in ['number', 'currency', 'percent']:
                field_metadata["Metadata"]["precision"] = field_config.get('precision', 18)
                field_metadata["Metadata"]["scale"] = field_config.get('scale', 0 if field_type == 'number' else 2)
            elif field_type == 'picklist':
                # Handle picklist values if provided
                values = field_config.get('picklist_values', ['Option 1', 'Option 2'])
                field_metadata["Metadata"]["valueSet"] = {
                    "valueSetDefinition": {
                        "value": [{"fullName": val, "default": i == 0} for i, val in enumerate(values)]
                    }
                }
            
            # Add description and required flag
            if field_config.get('description'):
                field_metadata["Metadata"]["description"] = field_config['description']
            
            if field_config.get('required', False):
                field_metadata["Metadata"]["required"] = True
            
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
                    if isinstance(error_json, list) and len(error_json) > 0:
                        error_details = error_json[0].get('message', error_details)
                    else:
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
            'errors': [],
            'manual_actions_needed': []
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
                    elif result.get('manual_creation_needed'):
                        results['manual_actions_needed'].append(result)
                        logger.warning(f"Manual creation needed for object: {object_name}")
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
            
            # Generate summary message
            if results['objects_created'] or results['fields_created']:
                summary_parts = []
                if results['objects_created']:
                    summary_parts.append(f"{len(results['objects_created'])} object(s) created")
                if results['fields_created']:
                    summary_parts.append(f"{len(results['fields_created'])} field(s) created")
                if results['manual_actions_needed']:
                    summary_parts.append(f"{len(results['manual_actions_needed'])} object(s) need manual creation")
                
                results['message'] = f"Configuration applied: {', '.join(summary_parts)}"
            else:
                results['message'] = "No objects or fields were created"
                if results['errors']:
                    results['success'] = False
            
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


def create_metadata_client(instance_url: str, access_token: str, salesforce_connection=None) -> SalesforceMetadataClient:
    """
    Factory function to create a Salesforce Metadata API client
    
    Args:
        instance_url (str): Salesforce instance URL
        access_token (str): Valid Salesforce access token
        salesforce_connection: Optional Salesforce connection object
        
    Returns:
        SalesforceMetadataClient: Configured client instance
    """
    return SalesforceMetadataClient(instance_url, access_token, salesforce_connection)
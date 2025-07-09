"""
Salesforce Metadata API client for programmatic custom object creation
Implements the CORRECT approach using SOAP-based Metadata API with zeep
"""
import logging
import requests
import json
import re
import subprocess
import tempfile
import os
import shutil
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
            # Check for local WSDL files first (recommended approach per ChatGPT)
            metadata_wsdl_path = None
            
            # Look for WSDL files in current directory
            local_wsdl_files = ['metadata.wsdl.xml', 'metadata.wsdl', 'salesforce_metadata.wsdl']
            for wsdl_file in local_wsdl_files:
                if os.path.exists(wsdl_file):
                    metadata_wsdl_path = wsdl_file
                    logger.info(f"Found local WSDL file: {wsdl_file}")
                    break
            
            if metadata_wsdl_path:
                # Use local WSDL file (more reliable per ChatGPT recommendation)
                self.soap_client = Client(metadata_wsdl_path)
                logger.info("✓ Successfully initialized SOAP client with local WSDL file")
            else:
                # Fallback to remote WSDL URL
                logger.info("No local WSDL found, attempting remote download...")
                logger.info("For better reliability, consider downloading WSDL files manually:")
                logger.info("Go to Setup → API → Generate WSDL → Download Metadata WSDL as 'metadata.wsdl.xml'")
                
                metadata_wsdl_url = f"{self.instance_url}/services/wsdl/metadata"
                
                # Create session with authentication - using Cookie-based auth for WSDL
                session = Session()
                session.headers.update({
                    'Cookie': f'sid={self.access_token}',
                    'SOAPAction': 'urn:create'
                })
                
                # Create transport and client
                transport = Transport(session=session)
                self.soap_client = Client(metadata_wsdl_url, transport=transport)
                
                logger.info("✓ Successfully initialized SOAP client with remote WSDL")
            
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
            
            # NEW APPROACH: Try SOAP Metadata API first, then CLI as fallback
            logger.info(f"Attempting to create custom object {api_name}__c via SOAP Metadata API")
            
            # Try SOAP Metadata API first
            soap_result = self._create_object_via_soap_metadata(api_name, label, plural_label, object_config)
            if soap_result.get('success'):
                return soap_result
            
            logger.info(f"SOAP method failed, trying Salesforce CLI fallback")
            
            # Fallback to SFDX CLI object creation
            return self._create_object_via_sfdx_cli(api_name, label, plural_label, object_config)
                
        except Exception as e:
            logger.error(f"Error creating custom object: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_object_via_soap_metadata(self, api_name: str, label: str, plural_label: str, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create custom object using SOAP Metadata API with XML generation
        
        Args:
            api_name (str): Object API name
            label (str): Object label
            plural_label (str): Object plural label
            object_config (dict): Object configuration
            
        Returns:
            dict: Creation result
        """
        try:
            # Import and create SOAP client
            from soap_metadata_client import create_soap_metadata_client
            
            soap_client = create_soap_metadata_client(self.instance_url, self.access_token)
            
            if not soap_client:
                return {
                    'success': False,
                    'error': 'Failed to initialize SOAP Metadata client'
                }
            
            # Prepare object configuration for SOAP client
            soap_config = {
                'api_name': api_name,
                'label': label,
                'pluralLabel': plural_label,
                'description': object_config.get('description', f"Custom object for {label.lower()}")
            }
            
            # Create custom object
            result = soap_client.create_custom_object(soap_config)
            
            if result.get('success'):
                logger.info(f"✓ Successfully created custom object {api_name}__c via SOAP Metadata API")
                return {
                    'success': True,
                    'object_name': f"{api_name}__c",
                    'object_label': label,
                    'method': 'soap_metadata',
                    'message': f"Custom object {label} created successfully via SOAP Metadata API"
                }
            else:
                logger.warning(f"SOAP Metadata API failed: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown SOAP error')
                }
                
        except Exception as e:
            logger.error(f"Error in SOAP Metadata creation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _try_tooling_api_object_creation(self, api_name: str, label: str, plural_label: str, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Try creating custom object via Tooling API - CORRECT implementation based on Salesforce docs
        """
        logger.warning("Custom object creation via API is not supported. Custom objects must be created manually through Salesforce Setup.")
        logger.info("This is a Salesforce platform limitation - the Tooling API does not support creating CustomObject metadata types.")
        
        # Return manual creation instructions immediately
        return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
    
    def _create_object_via_sfdx_cli(self, api_name: str, label: str, plural_label: str, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create custom object using Salesforce CLI (sfdx) via subprocess
        """
        try:
            logger.info(f"Creating custom object {api_name}__c via Salesforce CLI")
            
            # Check if sfdx CLI is available
            try:
                result = subprocess.run(['sf', '--version'], capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    logger.warning("Salesforce CLI (sf) not available, trying legacy sfdx command")
                    # Try legacy sfdx command
                    result = subprocess.run(['sfdx', '--version'], capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        logger.error("Neither 'sf' nor 'sfdx' CLI commands available")
                        return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
                    cli_command = 'sfdx'
                else:
                    cli_command = 'sf'
                    
                logger.info(f"Using Salesforce CLI: {cli_command}")
                
            except Exception as e:
                logger.error(f"Error checking CLI availability: {str(e)}")
                return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
            
            # First, authenticate or use existing auth
            # We'll use the access token we already have
            auth_result = self._authenticate_sfdx_cli(cli_command)
            if not auth_result:
                logger.error("Failed to authenticate with Salesforce CLI")
                return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
            
            # Create custom object using CLI
            object_name = f"{api_name}__c"
            description = object_config.get('description', f"Custom object for {label.lower()} management")
            
            # Build the CLI command using correct metadata approach
            if cli_command == 'sf':
                # Use sf schema generate sobject to create metadata files, then deploy
                return self._create_object_via_metadata_deployment(api_name, label, plural_label, object_config)
            else:
                # Legacy sfdx approach - create metadata files and deploy
                return self._create_object_via_metadata_deployment(api_name, label, plural_label, object_config)
            
            # This part was moved to _create_object_via_metadata_deployment
            # Call that method instead
                
        except subprocess.TimeoutExpired:
            logger.error("CLI command timed out")
            return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
        except Exception as e:
            logger.error(f"Error creating object via CLI: {str(e)}")
            return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
    
    def _authenticate_sfdx_cli(self, cli_command: str) -> bool:
        """
        Authenticate with Salesforce CLI using existing access token
        """
        try:
            # Use the correct auth command for newer SF CLI
            # Set SF_ACCESS_TOKEN environment variable and use --no-prompt
            auth_cmd = [
                cli_command, 'org', 'login', 'access-token',
                '--instance-url', self.instance_url,
                '--no-prompt',
                '--set-default'
            ]
            
            logger.debug(f"Authenticating CLI with: {' '.join(auth_cmd)}")
            
            # Set the access token via environment variable as required by CLI
            env = os.environ.copy()
            env['SF_ACCESS_TOKEN'] = self.access_token
            
            result = subprocess.run(
                auth_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            if result.returncode == 0:
                logger.info("✓ Successfully authenticated Salesforce CLI")
                return True
            else:
                logger.error(f"CLI authentication failed: {result.stderr or result.stdout}")
                
                # Try alternative authentication method
                return self._try_alternative_auth(cli_command)
                
        except Exception as e:
            logger.error(f"Error authenticating CLI: {str(e)}")
            return self._try_alternative_auth(cli_command)
    
    def _try_alternative_auth(self, cli_command: str) -> bool:
        """
        Try alternative authentication methods
        """
        try:
            # Method 1: Try with different flags
            logger.debug("Trying alternative auth with different flags")
            
            auth_cmd = [
                cli_command, 'org', 'login', 'access-token',
                '--instance-url', self.instance_url,
                '--no-prompt'
            ]
            
            env = os.environ.copy()
            env['SF_ACCESS_TOKEN'] = self.access_token
            
            result = subprocess.run(
                auth_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            if result.returncode == 0:
                logger.info("✓ Successfully authenticated with alternative method")
                return True
            
            # Method 2: Use sfdx auth:accesstoken:store if available
            logger.debug("Trying sfdx auth method")
            
            sfdx_auth_cmd = [
                'sfdx', 'auth:accesstoken:store',
                '--instanceurl', self.instance_url,
                '--setdefaultusername'
            ]
            
            result = subprocess.run(
                sfdx_auth_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                input=self.access_token + '\n'
            )
            
            if result.returncode == 0:
                logger.info("✓ Successfully authenticated with sfdx auth method")
                return True
            
            logger.warning("All authentication methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Error in alternative auth: {str(e)}")
            return False
    
    def _create_object_via_metadata_deployment(self, api_name: str, label: str, plural_label: str, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create custom object using metadata deployment via Salesforce CLI
        This is the CORRECT approach using sf schema generate sobject + sf project deploy
        """
        try:
            logger.info(f"Creating custom object {api_name}__c via metadata deployment")
            
            # Create a temporary directory for the SFDX project structure
            temp_dir = tempfile.mkdtemp(prefix='sf_metadata_')
            logger.debug(f"Created temp directory: {temp_dir}")
            
            try:
                # Initialize a basic SFDX project structure
                sfdx_project_json = {
                    "packageDirectories": [
                        {
                            "path": "force-app",
                            "default": True
                        }
                    ],
                    "namespace": "",
                    "sfdcLoginUrl": "https://login.salesforce.com",
                    "sourceApiVersion": "58.0"
                }
                
                # Create the project structure
                os.makedirs(os.path.join(temp_dir, "force-app", "main", "default", "objects"), exist_ok=True)
                
                # Write sfdx-project.json
                with open(os.path.join(temp_dir, "sfdx-project.json"), "w") as f:
                    json.dump(sfdx_project_json, f, indent=2)
                
                # Change to temp directory
                original_cwd = os.getcwd()
                os.chdir(temp_dir)
                
                try:
                    # Authenticate CLI first
                    auth_result = self._authenticate_sfdx_cli('sf')
                    if not auth_result:
                        logger.error("Failed to authenticate CLI for metadata deployment")
                        return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
                    
                    # Generate the custom object metadata using sf schema generate sobject
                    generate_cmd = [
                        'sf', 'schema', 'generate', 'sobject',
                        '--label', label,
                        '--use-default-features'  # Skip interactive prompts
                    ]
                    
                    logger.debug(f"Generating metadata: {' '.join(generate_cmd)}")
                    
                    # Execute schema generation
                    result = subprocess.run(
                        generate_cmd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        input=f"{api_name}\n{plural_label}\ny\n"  # Provide inputs for interactive prompts
                    )
                    
                    logger.debug(f"Schema generation result: {result.returncode}")
                    logger.debug(f"stdout: {result.stdout}")
                    if result.stderr:
                        logger.debug(f"stderr: {result.stderr}")
                    
                    if result.returncode != 0:
                        logger.error(f"Schema generation failed: {result.stderr or result.stdout}")
                        return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
                    
                    # First, check what orgs are available
                    org_list_result = subprocess.run(
                        ['sf', 'org', 'list'], 
                        capture_output=True, 
                        text=True, 
                        timeout=10
                    )
                    
                    # Use authenticated org or first available org
                    target_org = None
                    if org_list_result.returncode == 0 and org_list_result.stdout:
                        # Look for default org or use the first one
                        lines = org_list_result.stdout.split('\n')
                        for line in lines:
                            if 'default' in line.lower() or 'smartcart-dev-ed' in line or 'vs@abc.com' in line:
                                # Extract org alias/username from CLI output
                                # Format: │ 🍁 │       │ vs@abc.com │ 00DQy00000PzsecMAB │ Connected │
                                parts = [p.strip() for p in line.split('│') if p.strip()]
                                if len(parts) >= 3 and '@' in parts[2]:
                                    target_org = parts[2]  # Use the username
                                    break
                    
                    # If no specific org found, try without --target-org (uses default)
                    if target_org:
                        deploy_cmd = [
                            'sf', 'project', 'deploy', 'start',
                            '--source-dir', 'force-app/main/default/objects',
                            '--target-org', target_org
                        ]
                    else:
                        deploy_cmd = [
                            'sf', 'project', 'deploy', 'start',
                            '--source-dir', 'force-app/main/default/objects'
                        ]
                    
                    logger.debug(f"Deploying metadata: {' '.join(deploy_cmd)}")
                    
                    # Execute deployment
                    deploy_result = subprocess.run(
                        deploy_cmd,
                        capture_output=True,
                        text=True,
                        timeout=120  # Deployment can take longer
                    )
                    
                    logger.debug(f"Deployment result: {deploy_result.returncode}")
                    logger.debug(f"stdout: {deploy_result.stdout}")
                    if deploy_result.stderr:
                        logger.debug(f"stderr: {deploy_result.stderr}")
                    
                    if deploy_result.returncode == 0:
                        logger.info(f"✓ Successfully created and deployed custom object {api_name}__c")
                        return {
                            'success': True,
                            'object_name': f"{api_name}__c",
                            'object_label': label,
                            'message': f"Successfully created custom object '{label}' ({api_name}__c) via metadata deployment",
                            'cli_output': deploy_result.stdout,
                            'temp_dir': temp_dir  # Keep for debugging if needed
                        }
                    else:
                        error_msg = deploy_result.stderr or deploy_result.stdout or "Unknown deployment error"
                        logger.error(f"Deployment failed: {error_msg}")
                        return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
                        
                finally:
                    # Restore original directory
                    os.chdir(original_cwd)
                    
            except Exception as e:
                logger.error(f"Error in metadata deployment process: {str(e)}")
                return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
            
            finally:
                # Clean up temp directory
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp directory: {cleanup_error}")
                    
        except subprocess.TimeoutExpired:
            logger.error("Metadata deployment command timed out")
            return self._create_object_via_manual_fallback(api_name, label, plural_label, object_config)
        except Exception as e:
            logger.error(f"Error creating object via metadata deployment: {str(e)}")
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
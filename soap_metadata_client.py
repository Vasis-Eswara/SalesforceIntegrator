"""
SOAP-based Salesforce Metadata API client for direct programmatic deployment
Uses zeep library with proper XML metadata generation
"""

import logging
import os
import base64
import time
from typing import Dict, Any, Optional
from metadata_xml_generator import create_metadata_generator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import zeep
    from zeep import Client, Session, Transport
    from zeep.wsdl import wsdl
    ZEEP_AVAILABLE = True
    logger.info("zeep library found and imported successfully")
except ImportError as e:
    ZEEP_AVAILABLE = False
    logger.error(f"zeep library not available - SOAP client disabled: {str(e)}")
    logger.info("To enable SOAP functionality, install zeep: pip install zeep")

class SOAPMetadataClient:
    """
    Direct SOAP-based Salesforce Metadata API client
    Creates custom objects using XML metadata deployment
    """
    
    def __init__(self, instance_url: str, access_token: str):
        """
        Initialize SOAP Metadata client
        
        Args:
            instance_url (str): Salesforce instance URL
            access_token (str): Valid Salesforce access token
        """
        self.instance_url = instance_url.rstrip('/')
        self.access_token = access_token
        self.soap_client = None
        self.session_id = None
        self.metadata_generator = create_metadata_generator()
        
        # Initialize SOAP client
        self._initialize_soap_client()
    
    def _initialize_soap_client(self):
        """Initialize SOAP client with proper authentication"""
        if not ZEEP_AVAILABLE:
            logger.error("zeep library not available - cannot initialize SOAP client")
            return False
        
        try:
            # Check for local WSDL files first
            wsdl_path = None
            for wsdl_file in ['metadata.wsdl.xml', 'metadata.wsdl']:
                if os.path.exists(wsdl_file):
                    wsdl_path = wsdl_file
                    logger.info(f"Using local WSDL file: {wsdl_file}")
                    break
            
            if not wsdl_path:
                # Use remote WSDL
                wsdl_path = f"{self.instance_url}/services/wsdl/metadata"
                logger.info("Using remote WSDL URL")
            
            # Create authenticated session
            session = Session()
            session.headers.update({
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'urn:deploy'
            })
            
            # Create SOAP client
            transport = Transport(session=session)
            self.soap_client = Client(wsdl_path, transport=transport)
            
            # Set session ID for SOAP operations
            self.session_id = self.access_token
            
            logger.info("✓ SOAP Metadata client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SOAP client: {str(e)}")
            return False
    
    def create_custom_object(self, object_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create custom object using SOAP Metadata API
        
        Args:
            object_config (dict): Object configuration
            
        Returns:
            dict: Creation result
        """
        try:
            if not self.soap_client:
                return {
                    'success': False,
                    'error': 'SOAP client not initialized'
                }
            
            # Generate object metadata
            object_name = object_config.get('api_name', '').replace('__c', '')
            api_name = f"{object_name}__c"
            
            # Prepare XML metadata
            xml_config = {
                'label': object_config.get('label', object_name),
                'pluralLabel': object_config.get('pluralLabel', f"{object_name}s"),
                'description': object_config.get('description', f"Custom object for {object_name}")
            }
            
            # Generate XML
            object_xml = self.metadata_generator.generate_custom_object_xml(xml_config)
            
            logger.info(f"Generated XML metadata for {api_name}")
            logger.debug(f"Object XML:\n{object_xml}")
            
            # Create metadata package
            zip_content = self.metadata_generator.create_metadata_package(
                api_name, object_xml
            )
            
            # Deploy via SOAP
            result = self._deploy_metadata(zip_content)
            
            if result.get('success'):
                logger.info(f"✓ Successfully created custom object: {api_name}")
                return {
                    'success': True,
                    'object_name': api_name,
                    'message': f"Custom object {api_name} created successfully"
                }
            else:
                logger.error(f"Failed to create custom object: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown deployment error')
                }
                
        except Exception as e:
            logger.error(f"Error creating custom object: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_custom_field(self, object_name: str, field_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create custom field using SOAP Metadata API
        
        Args:
            object_name (str): Target object name
            field_config (dict): Field configuration
            
        Returns:
            dict: Creation result
        """
        try:
            if not self.soap_client:
                return {
                    'success': False,
                    'error': 'SOAP client not initialized'
                }
            
            # Generate field metadata
            field_name = field_config.get('api_name', '').replace('__c', '')
            api_name = f"{field_name}__c"
            
            # Prepare XML metadata
            xml_config = {
                'fullName': api_name,
                'label': field_config.get('label', field_name),
                'type': field_config.get('type', 'Text'),
                'length': field_config.get('length', 255),
                'required': field_config.get('required', False),
                'description': field_config.get('description', f"Custom field {field_name}")
            }
            
            # Generate XML
            field_xml = self.metadata_generator.generate_custom_field_xml(xml_config)
            
            logger.info(f"Generated XML metadata for field {api_name}")
            logger.debug(f"Field XML:\n{field_xml}")
            
            # Create metadata package with field
            zip_content = self.metadata_generator.create_metadata_package(
                object_name, "", {api_name: field_xml}
            )
            
            # Deploy via SOAP
            result = self._deploy_metadata(zip_content)
            
            if result.get('success'):
                logger.info(f"✓ Successfully created custom field: {api_name}")
                return {
                    'success': True,
                    'field_name': api_name,
                    'message': f"Custom field {api_name} created successfully"
                }
            else:
                logger.error(f"Failed to create custom field: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown deployment error')
                }
                
        except Exception as e:
            logger.error(f"Error creating custom field: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _deploy_metadata(self, zip_content: str) -> Dict[str, Any]:
        """
        Deploy metadata package via SOAP
        
        Args:
            zip_content (str): Base64 encoded zip file content
            
        Returns:
            dict: Deployment result
        """
        try:
            # Prepare deployment request
            deploy_options = {
                'allowMissingFiles': False,
                'autoUpdatePackage': False,
                'checkOnly': False,
                'ignoreWarnings': False,
                'performRetrieve': False,
                'purgeOnDelete': False,
                'rollbackOnError': True,
                'singlePackage': True
            }
            
            # Create deployment request
            deployment_request = {
                'sessionId': self.session_id,
                'zipFile': zip_content,
                'deployOptions': deploy_options
            }
            
            logger.info("Deploying metadata package...")
            
            # Call SOAP deploy method
            response = self.soap_client.service.deploy(**deployment_request)
            
            if hasattr(response, 'id'):
                deployment_id = response.id
                logger.info(f"Deployment started with ID: {deployment_id}")
                
                # Check deployment status
                return self._check_deployment_status(deployment_id)
            else:
                return {
                    'success': False,
                    'error': 'No deployment ID returned'
                }
                
        except Exception as e:
            logger.error(f"SOAP deployment failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        Check deployment status until completion
        
        Args:
            deployment_id (str): Deployment ID
            
        Returns:
            dict: Final deployment result
        """
        try:
            max_attempts = 30
            attempt = 0
            
            while attempt < max_attempts:
                logger.info(f"Checking deployment status (attempt {attempt + 1}/{max_attempts})...")
                
                # Check status
                status_response = self.soap_client.service.checkDeployStatus(
                    sessionId=self.session_id,
                    asyncProcessId=deployment_id
                )
                
                if hasattr(status_response, 'done') and status_response.done:
                    if hasattr(status_response, 'success') and status_response.success:
                        logger.info("✓ Deployment completed successfully")
                        return {
                            'success': True,
                            'deployment_id': deployment_id
                        }
                    else:
                        error_msg = "Deployment failed"
                        if hasattr(status_response, 'details'):
                            error_msg = f"Deployment failed: {status_response.details}"
                        logger.error(error_msg)
                        return {
                            'success': False,
                            'error': error_msg
                        }
                
                # Wait before next check
                time.sleep(2)
                attempt += 1
            
            return {
                'success': False,
                'error': 'Deployment timeout - status check exceeded maximum attempts'
            }
            
        except Exception as e:
            logger.error(f"Error checking deployment status: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def create_soap_metadata_client(instance_url: str, access_token: str) -> Optional[SOAPMetadataClient]:
    """
    Factory function to create SOAP Metadata client
    
    Args:
        instance_url (str): Salesforce instance URL
        access_token (str): Valid access token
        
    Returns:
        SOAPMetadataClient or None: Initialized client or None if failed
    """
    try:
        client = SOAPMetadataClient(instance_url, access_token)
        if client.soap_client:
            return client
        else:
            logger.error("Failed to initialize SOAP client")
            return None
    except Exception as e:
        logger.error(f"Error creating SOAP client: {str(e)}")
        return None
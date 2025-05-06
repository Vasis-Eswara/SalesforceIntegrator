import os
import logging
import requests
import tempfile
import base64
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)

# Salesforce configuration
SF_CLIENT_ID = os.environ.get('SALESFORCE_CLIENT_ID', '')
SF_CLIENT_SECRET = os.environ.get('SALESFORCE_CLIENT_SECRET', '')
SF_REDIRECT_URI = os.environ.get('SALESFORCE_REDIRECT_URI', '')
SF_CLIENT_DOMAIN = os.environ.get('SALESFORCE_DOMAIN', '')

# Default to production login URL if no domain specified
if SF_CLIENT_DOMAIN and SF_CLIENT_DOMAIN.strip():
    domain = SF_CLIENT_DOMAIN.strip()
    if domain.startswith('http'):
        SF_LOGIN_URL = domain
    else:
        SF_LOGIN_URL = f"https://{domain}"
    logger.debug(f"Using custom Salesforce domain (SOAP): {SF_LOGIN_URL}")
else:
    SF_LOGIN_URL = 'https://login.salesforce.com'
    logger.debug(f"Using production Salesforce login URL (SOAP): {SF_LOGIN_URL}")

# SOAP API endpoints
SOAP_LOGIN_URL = f"{SF_LOGIN_URL}/services/Soap/u/58.0"
# Enterprise WSDL URL will be constructed from instance_url during use

class SalesforceSOAPClient:
    """
    Client for interacting with Salesforce SOAP API
    """
    def __init__(self, username=None, password=None, security_token=None, 
                 session_id=None, instance_url=None):
        self.username = username
        self.password = password
        self.security_token = security_token
        self.session_id = session_id
        self.instance_url = instance_url
        self.client = None
        self.headers = None

    def login_with_soap(self):
        """
        Login to Salesforce using SOAP API with username and password
        """
        if not self.username or not self.password:
            raise ValueError("Username and password are required for SOAP login")
            
        try:
            # Direct SOAP request without using WSDL
            login_url = SOAP_LOGIN_URL
            password_with_token = f"{self.password}{self.security_token or ''}"
            
            # XML request template
            soap_request = f'''
            <?xml version="1.0" encoding="utf-8" ?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:urn="urn:partner.soap.sforce.com">
                <soapenv:Body>
                    <urn:login>
                        <urn:username>{self.username}</urn:username>
                        <urn:password>{password_with_token}</urn:password>
                    </urn:login>
                </soapenv:Body>
            </soapenv:Envelope>
            '''.strip()
            
            headers = {
                'Content-Type': 'text/xml; charset=UTF-8',
                'SOAPAction': '""'
            }
            
            response = requests.post(login_url, data=soap_request, headers=headers)
            
            # Check for errors
            if response.status_code != 200:
                error_message = f"SOAP login failed with status {response.status_code}: {response.text}"
                logger.error(error_message)
                raise Exception(error_message)
            
            # Parse XML response manually
            import xml.etree.ElementTree as ET
            # Add namespace prefix mapping
            namespaces = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'partner': 'urn:partner.soap.sforce.com'
            }
            
            root = ET.fromstring(response.content)
            
            # Extract sessionId and serverUrl
            result = root.find('.//partner:loginResponse/partner:result', namespaces)
            if result is None:
                raise Exception("Could not find login result in SOAP response")
                
            session_id = result.find('./partner:sessionId', namespaces)
            server_url = result.find('./partner:serverUrl', namespaces)
            
            if session_id is None or server_url is None:
                raise Exception("Missing sessionId or serverUrl in login response")
                
            self.session_id = session_id.text
            self.instance_url = server_url.text.split('/services/')[0]
            
            self.headers = {
                'SessionId': self.session_id,
                'Content-Type': 'text/xml;charset=UTF-8',
                'SOAPAction': '""'
            }
            
            logger.debug(f"Successfully logged in via SOAP API. Instance URL: {self.instance_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error during SOAP login: {str(e)}")
            raise Exception(f"SOAP login error: {str(e)}")

    def login_with_oauth_token(self, access_token, instance_url):
        """
        Initialize SOAP client using an OAuth access token
        """
        self.session_id = access_token
        self.instance_url = instance_url
        
        self.headers = {
            'SessionId': self.session_id,
            'Content-Type': 'text/xml;charset=UTF-8',
            'SOAPAction': '""'
        }
        
        logger.debug(f"Initialized SOAP client with OAuth token. Instance URL: {self.instance_url}")
        return True

    def get_user_info(self):
        """
        Get information about the currently logged in user
        """
        if not self.session_id or not self.instance_url:
            raise ValueError("Not authenticated. Call login_with_soap or login_with_oauth_token first.")
        
        try:
            # Direct SOAP request
            endpoint = f"{self.instance_url}/services/Soap/u/58.0"
            
            # XML request template for getUserInfo
            soap_request = f'''
            <?xml version="1.0" encoding="utf-8" ?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:urn="urn:partner.soap.sforce.com">
                <soapenv:Header>
                    <urn:SessionHeader>
                        <urn:sessionId>{self.session_id}</urn:sessionId>
                    </urn:SessionHeader>
                </soapenv:Header>
                <soapenv:Body>
                    <urn:getUserInfo />
                </soapenv:Body>
            </soapenv:Envelope>
            '''.strip()
            
            headers = {
                'Content-Type': 'text/xml; charset=UTF-8',
                'SOAPAction': '""'
            }
            
            response = requests.post(endpoint, data=soap_request, headers=headers)
            
            # Check for errors
            if response.status_code != 200:
                error_message = f"SOAP getUserInfo failed with status {response.status_code}: {response.text}"
                logger.error(error_message)
                raise Exception(error_message)
            
            # Parse XML response manually
            import xml.etree.ElementTree as ET
            # Add namespace prefix mapping
            namespaces = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'partner': 'urn:partner.soap.sforce.com'
            }
            
            root = ET.fromstring(response.content)
            
            # Find the result element
            result = root.find('.//partner:getUserInfoResponse/partner:result', namespaces)
            
            if result is None:
                raise Exception("Could not find getUserInfo result in SOAP response")
            
            # Extract user info fields
            user_id = result.find('./partner:userId', namespaces)
            org_id = result.find('./partner:organizationId', namespaces)
            username = result.find('./partner:userName', namespaces)
            email = result.find('./partner:userEmail', namespaces)
            full_name = result.find('./partner:userFullName', namespaces)
            language = result.find('./partner:userLanguage', namespaces)
            locale = result.find('./partner:userLocale', namespaces)
            timezone = result.find('./partner:userTimeZone', namespaces)
            
            user_info = {
                'user_id': user_id.text if user_id is not None else None,
                'org_id': org_id.text if org_id is not None else None,
                'username': username.text if username is not None else None,
                'email': email.text if email is not None else None,
                'full_name': full_name.text if full_name is not None else None,
                'language': language.text if language is not None else None,
                'locale': locale.text if locale is not None else None,
                'timezone': timezone.text if timezone is not None else None,
            }
            
            return user_info
            
        except Exception as e:
            logger.error(f"Error getting user info via SOAP: {str(e)}")
            raise Exception(f"SOAP getUserInfo error: {str(e)}")

    def query(self, soql_query):
        """
        Execute a SOQL query using the SOAP API
        """
        if not self.session_id or not self.instance_url:
            raise ValueError("Not authenticated. Call login_with_soap or login_with_oauth_token first.")
        
        try:
            # Direct SOAP request
            endpoint = f"{self.instance_url}/services/Soap/u/58.0"
            
            # XML request template for query
            soap_request = f'''
            <?xml version="1.0" encoding="utf-8" ?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:urn="urn:partner.soap.sforce.com">
                <soapenv:Header>
                    <urn:SessionHeader>
                        <urn:sessionId>{self.session_id}</urn:sessionId>
                    </urn:SessionHeader>
                </soapenv:Header>
                <soapenv:Body>
                    <urn:query>
                        <urn:queryString>{soql_query}</urn:queryString>
                    </urn:query>
                </soapenv:Body>
            </soapenv:Envelope>
            '''.strip()
            
            headers = {
                'Content-Type': 'text/xml; charset=UTF-8',
                'SOAPAction': '""'
            }
            
            response = requests.post(endpoint, data=soap_request, headers=headers)
            
            # Check for errors
            if response.status_code != 200:
                error_message = f"SOAP query failed with status {response.status_code}: {response.text}"
                logger.error(error_message)
                raise Exception(error_message)
            
            # Parse XML response manually
            import xml.etree.ElementTree as ET
            # Add namespace prefix mapping
            namespaces = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'partner': 'urn:partner.soap.sforce.com'
            }
            
            root = ET.fromstring(response.content)
            
            # Find the result element
            result = root.find('.//partner:queryResponse/partner:result', namespaces)
            
            if result is None:
                raise Exception("Could not find query result in SOAP response")
            
            # Process query result
            records = []
            result_records = result.findall('./partner:records', namespaces)
            
            # Get the query more info
            done_elem = result.find('./partner:done', namespaces)
            done = False
            if done_elem is not None and done_elem.text:
                done = done_elem.text.lower() == 'true'
            query_locator_elem = result.find('./partner:queryLocator', namespaces)
            query_locator = query_locator_elem.text if query_locator_elem is not None else None
            
            # Process records
            for record in result_records:
                record_data = {}
                
                # Get type
                type_attr = record.get('{http://www.w3.org/2001/XMLSchema-instance}type')
                if type_attr:
                    # Strip namespace prefix if present
                    record_type = type_attr.split(':')[-1]
                    record_data['type'] = record_type
                
                # Extract all field values
                for field in record:
                    # Skip attributes and nested records
                    if field.tag.endswith('type') or field.tag.endswith('Id'):
                        record_data[field.tag.split('}')[-1]] = field.text
                    elif not field.tag.endswith('records'):
                        field_name = field.tag.split('}')[-1]
                        record_data[field_name] = field.text
                
                records.append(record_data)
            
            # Handle pagination if needed
            while not done and query_locator:
                # Make queryMore request
                soap_request = f'''
                <?xml version="1.0" encoding="utf-8" ?>
                <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                               xmlns:urn="urn:partner.soap.sforce.com">
                    <soapenv:Header>
                        <urn:SessionHeader>
                            <urn:sessionId>{self.session_id}</urn:sessionId>
                        </urn:SessionHeader>
                    </soapenv:Header>
                    <soapenv:Body>
                        <urn:queryMore>
                            <urn:queryLocator>{query_locator}</urn:queryLocator>
                        </urn:queryMore>
                    </soapenv:Body>
                </soapenv:Envelope>
                '''.strip()
                
                response = requests.post(endpoint, data=soap_request, headers=headers)
                
                # Check for errors
                if response.status_code != 200:
                    logger.warning(f"SOAP queryMore failed with status {response.status_code}: {response.text}")
                    break
                
                # Parse response
                root = ET.fromstring(response.content)
                result = root.find('.//partner:queryMoreResponse/partner:result', namespaces)
                
                if result is None:
                    break
                
                # Process additional records
                result_records = result.findall('./partner:records', namespaces)
                
                # Update pagination info
                done_elem = result.find('./partner:done', namespaces)
                done = False
                if done_elem is not None and done_elem.text:
                    done = done_elem.text.lower() == 'true'
                query_locator_elem = result.find('./partner:queryLocator', namespaces)
                query_locator = query_locator_elem.text if query_locator_elem is not None else None
                
                # Process records
                for record in result_records:
                    record_data = {}
                    
                    # Get type
                    type_attr = record.get('{http://www.w3.org/2001/XMLSchema-instance}type')
                    if type_attr:
                        # Strip namespace prefix if present
                        record_type = type_attr.split(':')[-1]
                        record_data['type'] = record_type
                    
                    # Extract all field values
                    for field in record:
                        # Skip attributes and nested records
                        if field.tag.endswith('type') or field.tag.endswith('Id'):
                            record_data[field.tag.split('}')[-1]] = field.text
                        elif not field.tag.endswith('records'):
                            field_name = field.tag.split('}')[-1]
                            record_data[field_name] = field.text
                    
                    records.append(record_data)
            
            return records
            
        except Exception as e:
            logger.error(f"Error executing query via SOAP: {str(e)}")
            raise Exception(f"SOAP query error: {str(e)}")

    def describe_sobject(self, object_name):
        """
        Get metadata about a Salesforce object
        """
        if not self.session_id or not self.instance_url:
            raise ValueError("Not authenticated. Call login_with_soap or login_with_oauth_token first.")
        
        try:
            # Direct SOAP request
            endpoint = f"{self.instance_url}/services/Soap/u/58.0"
            
            # XML request template for describeSObject
            soap_request = f'''
            <?xml version="1.0" encoding="utf-8" ?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:urn="urn:partner.soap.sforce.com">
                <soapenv:Header>
                    <urn:SessionHeader>
                        <urn:sessionId>{self.session_id}</urn:sessionId>
                    </urn:SessionHeader>
                </soapenv:Header>
                <soapenv:Body>
                    <urn:describeSObject>
                        <urn:sObjectType>{object_name}</urn:sObjectType>
                    </urn:describeSObject>
                </soapenv:Body>
            </soapenv:Envelope>
            '''.strip()
            
            headers = {
                'Content-Type': 'text/xml; charset=UTF-8',
                'SOAPAction': '""'
            }
            
            response = requests.post(endpoint, data=soap_request, headers=headers)
            
            # Check for errors
            if response.status_code != 200:
                error_message = f"SOAP describeSObject failed with status {response.status_code}: {response.text}"
                logger.error(error_message)
                raise Exception(error_message)
            
            # Parse XML response manually
            import xml.etree.ElementTree as ET
            # Add namespace prefix mapping
            namespaces = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'partner': 'urn:partner.soap.sforce.com'
            }
            
            root = ET.fromstring(response.content)
            
            # Find the result element
            result = root.find('.//partner:describeSObjectResponse/partner:result', namespaces)
            
            if result is None:
                raise Exception("Could not find describeSObject result in SOAP response")
                
            # Extract basic object info
            name = result.find('./partner:name', namespaces)
            label = result.find('./partner:label', namespaces)
            
            object_info = {
                'name': name.text if name is not None else object_name,
                'label': label.text if label is not None else object_name,
                'fields': []
            }
            
            # Extract fields
            fields = result.findall('./partner:fields', namespaces)
            
            for field in fields:
                field_name = field.find('./partner:name', namespaces)
                field_label = field.find('./partner:label', namespaces)
                field_type = field.find('./partner:type', namespaces)
                field_nillable = field.find('./partner:nillable', namespaces)
                field_defaultedOnCreate = field.find('./partner:defaultedOnCreate', namespaces)
                field_unique = field.find('./partner:unique', namespaces)
                field_custom = field.find('./partner:custom', namespaces)
                field_updatable = field.find('./partner:updateable', namespaces)
                field_defaultValue = field.find('./partner:defaultValue', namespaces)
                
                if field_name is not None:
                    # Define field properties safely with None checks
                    is_required = False
                    if field_nillable is not None and field_nillable.text:
                        nillable = field_nillable.text.lower() == 'false'
                        if field_defaultedOnCreate is not None and field_defaultedOnCreate.text:
                            defaulted = field_defaultedOnCreate.text.lower() == 'false'
                            is_required = nillable and defaulted
                    
                    is_unique = False
                    if field_unique is not None and field_unique.text:
                        is_unique = field_unique.text.lower() == 'true'
                    
                    is_custom = False
                    if field_custom is not None and field_custom.text:
                        is_custom = field_custom.text.lower() == 'true'
                    
                    is_updateable = False
                    if field_updatable is not None and field_updatable.text:
                        is_updateable = field_updatable.text.lower() == 'true'
                    
                    field_info = {
                        'name': field_name.text,
                        'label': field_label.text if field_label is not None else field_name.text,
                        'type': field_type.text if field_type is not None else 'string',
                        'required': is_required,
                        'unique': is_unique,
                        'custom': is_custom,
                        'updateable': is_updateable,
                        'defaultValue': field_defaultValue.text if field_defaultValue is not None else None
                    }
                    
                    # Get relationship info if it's a reference field
                    if field_type is not None and field_type.text == 'reference':
                        relationshipName = field.find('./partner:relationshipName', namespaces)
                        referenceTo = field.findall('./partner:referenceTo', namespaces)
                        
                        if relationshipName is not None:
                            field_info['relationshipName'] = relationshipName.text
                        
                        if referenceTo:
                            field_info['referenceTo'] = [ref.text for ref in referenceTo if ref.text]
                    
                    # Get picklist values if applicable
                    if field_type is not None and field_type.text in ('picklist', 'multipicklist'):
                        picklistValues = field.findall('./partner:picklistValues', namespaces)
                        field_info['picklistValues'] = []
                        
                        for pv in picklistValues:
                            value = pv.find('./partner:value', namespaces)
                            active = pv.find('./partner:active', namespaces)
                            
                            is_active = False
                            if active is not None and active.text:
                                is_active = active.text.lower() == 'true'
                                
                            if value is not None and is_active:
                                field_info['picklistValues'].append(value.text)
                    
                    # Add length for string fields
                    if field_type is not None and field_type.text in ('string', 'textarea'):
                        length = field.find('./partner:length', namespaces)
                        if length is not None:
                            if length.text is not None:
                                try:
                                    field_info['length'] = int(length.text)
                                except (ValueError, TypeError):
                                    field_info['length'] = 0
                            else:
                                field_info['length'] = 0
                    
                    # Add precision and scale for numeric fields
                    if field_type is not None and field_type.text in ('double', 'currency', 'percent'):
                        precision = field.find('./partner:precision', namespaces)
                        scale = field.find('./partner:scale', namespaces)
                        
                        if precision is not None:
                            if precision.text is not None:
                                try:
                                    field_info['precision'] = int(precision.text)
                                except (ValueError, TypeError):
                                    field_info['precision'] = 0
                            else:
                                field_info['precision'] = 0
                        if scale is not None:
                            if scale.text is not None:
                                try:
                                    field_info['scale'] = int(scale.text)
                                except (ValueError, TypeError):
                                    field_info['scale'] = 0
                            else:
                                field_info['scale'] = 0
                    
                    object_info['fields'].append(field_info)
            
            return object_info
            
        except Exception as e:
            logger.error(f"Error describing object via SOAP: {str(e)}")
            raise Exception(f"SOAP describeSObject error: {str(e)}")
            
    def create(self, sobject_type, sobject_data):
        """
        Create a record in Salesforce
        """
        if not self.session_id or not self.instance_url:
            raise ValueError("Not authenticated. Call login_with_soap or login_with_oauth_token first.")
        
        try:
            # Direct SOAP request
            endpoint = f"{self.instance_url}/services/Soap/u/58.0"
            
            # Build field XML
            fields_xml = ''
            for field, value in sobject_data.items():
                # Skip None values
                if value is None:
                    continue
                    
                # Format value based on type
                if isinstance(value, bool):
                    formatted_value = str(value).lower()
                elif isinstance(value, (int, float)):
                    formatted_value = str(value)
                else:
                    # Escape XML special characters
                    formatted_value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace('\'', '&apos;')
                    
                fields_xml += f"<{field}>{formatted_value}</{field}>\n"
            
            # XML request template for create
            soap_request = f'''
            <?xml version="1.0" encoding="utf-8" ?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:urn="urn:partner.soap.sforce.com"
                           xmlns:urn1="urn:sobject.partner.soap.sforce.com">
                <soapenv:Header>
                    <urn:SessionHeader>
                        <urn:sessionId>{self.session_id}</urn:sessionId>
                    </urn:SessionHeader>
                </soapenv:Header>
                <soapenv:Body>
                    <urn:create>
                        <urn:sObjects xsi:type="urn1:{sobject_type}">
                            {fields_xml}
                        </urn:sObjects>
                    </urn:create>
                </soapenv:Body>
            </soapenv:Envelope>
            '''.strip()
            
            headers = {
                'Content-Type': 'text/xml; charset=UTF-8',
                'SOAPAction': '""'
            }
            
            response = requests.post(endpoint, data=soap_request, headers=headers)
            
            # Check for errors
            if response.status_code != 200:
                error_message = f"SOAP create failed with status {response.status_code}: {response.text}"
                logger.error(error_message)
                raise Exception(error_message)
            
            # Parse XML response manually
            import xml.etree.ElementTree as ET
            # Add namespace prefix mapping
            namespaces = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'partner': 'urn:partner.soap.sforce.com'
            }
            
            root = ET.fromstring(response.content)
            
            # Find the result element
            result = root.find('.//partner:createResponse/partner:result', namespaces)
            
            if result is None:
                raise Exception("Could not find create result in SOAP response")
            
            # Process result
            success_elem = result.find('./partner:success', namespaces)
            success = False
            if success_elem is not None and success_elem.text:
                success = success_elem.text.lower() == 'true'
                
            if success:
                id_elem = result.find('./partner:id', namespaces)
                record_id = id_elem.text if id_elem is not None else None
                
                return {
                    'id': record_id,
                    'success': True
                }
            else:
                # Process errors
                errors = []
                error_elems = result.findall('./partner:errors', namespaces)
                
                for error in error_elems:
                    message = error.find('./partner:message', namespaces)
                    fields = error.findall('./partner:fields', namespaces)
                    status_code = error.find('./partner:statusCode', namespaces)
                    
                    error_info = {
                        'message': message.text if message is not None else 'Unknown error',
                        'fields': [field.text for field in fields if field.text],
                        'statusCode': status_code.text if status_code is not None else 'UNKNOWN_ERROR'
                    }
                    
                    errors.append(error_info)
                
                return {
                    'success': False,
                    'errors': errors
                }
                
        except Exception as e:
            logger.error(f"Error creating record via SOAP: {str(e)}")
            raise Exception(f"SOAP create error: {str(e)}")
    
    def create_multiple(self, sobject_type, records):
        """
        Create multiple records in Salesforce
        """
        if not self.session_id or not self.instance_url:
            raise ValueError("Not authenticated. Call login_with_soap or login_with_oauth_token first.")
            
        try:
            # For up to 200 records at once (Salesforce limit)
            max_batch_size = 200
            all_results = {
                'success': 0,
                'failure': 0,
                'errors': [],
                'created_ids': []
            }
            
            # Process in batches if needed
            for i in range(0, len(records), max_batch_size):
                batch = records[i:i + max_batch_size]
                
                # Direct SOAP request
                endpoint = f"{self.instance_url}/services/Soap/u/58.0"
                
                # Build sObjects XML
                sobjects_xml = ''
                for record in batch:
                    fields_xml = ''
                    for field, value in record.items():
                        # Skip None values
                        if value is None:
                            continue
                            
                        # Format value based on type
                        if isinstance(value, bool):
                            formatted_value = str(value).lower()
                        elif isinstance(value, (int, float)):
                            formatted_value = str(value)
                        else:
                            # Escape XML special characters
                            formatted_value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace('\'', '&apos;')
                            
                        fields_xml += f"<{field}>{formatted_value}</{field}>\n"
                    
                    sobjects_xml += f'''
                    <urn:sObjects xsi:type="urn1:{sobject_type}">
                        {fields_xml}
                    </urn:sObjects>
                    '''
                
                # XML request template for create
                soap_request = f'''
                <?xml version="1.0" encoding="utf-8" ?>
                <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                               xmlns:urn="urn:partner.soap.sforce.com"
                               xmlns:urn1="urn:sobject.partner.soap.sforce.com">
                    <soapenv:Header>
                        <urn:SessionHeader>
                            <urn:sessionId>{self.session_id}</urn:sessionId>
                        </urn:SessionHeader>
                    </soapenv:Header>
                    <soapenv:Body>
                        <urn:create>
                            {sobjects_xml}
                        </urn:create>
                    </soapenv:Body>
                </soapenv:Envelope>
                '''.strip()
                
                headers = {
                    'Content-Type': 'text/xml; charset=UTF-8',
                    'SOAPAction': '""'
                }
                
                response = requests.post(endpoint, data=soap_request, headers=headers)
                
                # Check for errors
                if response.status_code != 200:
                    error_message = f"SOAP create_multiple failed with status {response.status_code}: {response.text}"
                    logger.error(error_message)
                    raise Exception(error_message)
                
                # Parse XML response manually
                import xml.etree.ElementTree as ET
                # Add namespace prefix mapping
                namespaces = {
                    'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                    'partner': 'urn:partner.soap.sforce.com'
                }
                
                root = ET.fromstring(response.content)
                
                # Find the result elements
                results = root.findall('.//partner:createResponse/partner:result', namespaces)
                
                if not results:
                    raise Exception("Could not find create results in SOAP response")
                
                # Process results
                for result in results:
                    success_elem = result.find('./partner:success', namespaces)
                    success = False
                    if success_elem is not None and success_elem.text:
                        success = success_elem.text.lower() == 'true'
                    
                    if success:
                        all_results['success'] += 1
                        id_elem = result.find('./partner:id', namespaces)
                        if id_elem is not None and id_elem.text:
                            all_results['created_ids'].append(id_elem.text)
                    else:
                        all_results['failure'] += 1
                        error_elems = result.findall('./partner:errors', namespaces)
                        
                        for error in error_elems:
                            message = error.find('./partner:message', namespaces)
                            fields = error.findall('./partner:fields', namespaces)
                            status_code = error.find('./partner:statusCode', namespaces)
                            
                            error_info = {
                                'message': message.text if message is not None else 'Unknown error',
                                'fields': [field.text for field in fields if field.text],
                                'statusCode': status_code.text if status_code is not None else 'UNKNOWN_ERROR'
                            }
                            
                            all_results['errors'].append(error_info)
            
            return all_results
                
        except Exception as e:
            logger.error(f"Error creating multiple records via SOAP: {str(e)}")
            raise Exception(f"SOAP create_multiple error: {str(e)}")
    
    def _get_login_wsdl(self):
        """
        Generate a login WSDL file for Salesforce authentication
        """
        login_wsdl_content = '''<?xml version="1.0" encoding="UTF-8"?>
<definitions targetNamespace="urn:partner.soap.sforce.com"
            xmlns="http://schemas.xmlsoap.org/wsdl/"
            xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
            xmlns:tns="urn:partner.soap.sforce.com"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <types>
        <schema elementFormDefault="qualified" targetNamespace="urn:partner.soap.sforce.com"
                xmlns="http://www.w3.org/2001/XMLSchema">
            <element name="login">
                <complexType>
                    <sequence>
                        <element name="username" type="xsd:string"/>
                        <element name="password" type="xsd:string"/>
                    </sequence>
                </complexType>
            </element>
            <element name="loginResponse">
                <complexType>
                    <sequence>
                        <element name="result" type="tns:LoginResult"/>
                    </sequence>
                </complexType>
            </element>
            <complexType name="LoginResult">
                <sequence>
                    <element name="metadataServerUrl" type="xsd:string"/>
                    <element name="passwordExpired" type="xsd:boolean"/>
                    <element name="sandbox" type="xsd:boolean"/>
                    <element name="serverUrl" type="xsd:string"/>
                    <element name="sessionId" type="xsd:string"/>
                    <element name="userId" type="xsd:string"/>
                    <element name="userInfo" type="tns:UserInfo" minOccurs="0"/>
                </sequence>
            </complexType>
            <complexType name="UserInfo">
                <sequence>
                    <element name="accessibilityMode" type="xsd:boolean"/>
                    <element name="chatterExternal" type="xsd:boolean" minOccurs="0"/>
                    <element name="currencySymbol" type="xsd:string" nillable="true"/>
                    <element name="orgAttachmentFileSizeLimit" type="xsd:int"/>
                    <element name="orgDefaultCurrencyIsoCode" type="xsd:string" nillable="true"/>
                    <element name="orgDefaultCurrencyLocale" type="xsd:string" minOccurs="0"/>
                    <element name="orgDisallowHtmlAttachments" type="xsd:boolean"/>
                    <element name="orgHasPersonAccounts" type="xsd:boolean"/>
                    <element name="organizationId" type="xsd:string"/>
                    <element name="organizationMultiCurrency" type="xsd:boolean"/>
                    <element name="organizationName" type="xsd:string"/>
                    <element name="profileId" type="xsd:string"/>
                    <element name="roleId" type="xsd:string" nillable="true"/>
                    <element name="sessionSecondsValid" type="xsd:int" minOccurs="0"/>
                    <element name="userDefaultCurrencyIsoCode" type="xsd:string" nillable="true"/>
                    <element name="userEmail" type="xsd:string"/>
                    <element name="userFullName" type="xsd:string"/>
                    <element name="userId" type="xsd:string"/>
                    <element name="userLanguage" type="xsd:string"/>
                    <element name="userLocale" type="xsd:string"/>
                    <element name="userName" type="xsd:string"/>
                    <element name="userTimeZone" type="xsd:string"/>
                    <element name="userType" type="xsd:string"/>
                    <element name="userUiSkin" type="xsd:string" minOccurs="0"/>
                </sequence>
            </complexType>
        </schema>
    </types>
    <message name="loginRequest">
        <part element="tns:login" name="parameters"/>
    </message>
    <message name="loginResponse">
        <part element="tns:loginResponse" name="parameters"/>
    </message>
    <portType name="Soap">
        <operation name="login">
            <input message="tns:loginRequest"/>
            <output message="tns:loginResponse"/>
        </operation>
    </portType>
    <binding name="SoapBinding" type="tns:Soap">
        <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
        <operation name="login">
            <soap:operation soapAction=""/>
            <input>
                <soap:body use="literal"/>
            </input>
            <output>
                <soap:body use="literal"/>
            </output>
        </operation>
    </binding>
    <service name="SforceService">
        <port binding="tns:SoapBinding" name="Soap">
            <soap:address location="https://login.salesforce.com/services/Soap/u/58.0"/>
        </port>
    </service>
</definitions>'''
        
        # Update the SOAP endpoint to match the configured URL
        if SOAP_LOGIN_URL:
            login_wsdl_content = login_wsdl_content.replace(
                'https://login.salesforce.com/services/Soap/u/58.0',
                SOAP_LOGIN_URL
            )
        
        # Create a temporary file for the WSDL
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wsdl', delete=False) as temp:
            temp.write(login_wsdl_content)
            temp_path = temp.name
            
        return temp_path
        
    def _get_enterprise_wsdl(self):
        """
        Get the Enterprise WSDL content
        
        In a real implementation, this would download from Salesforce or use a cached version.
        For this example, we're using a simplified WSDL stub.
        """
        # TODO: In production, download actual WSDL or use a cached version
        # For now, we'll implement a simplified stub that enables basic operations
        enterprise_wsdl_content = '''<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" 
            xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/" 
            xmlns:tns="urn:enterprise.soap.sforce.com" 
            xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
            targetNamespace="urn:enterprise.soap.sforce.com">
            <types>
                <schema xmlns="http://www.w3.org/2001/XMLSchema" 
                         elementFormDefault="qualified" 
                         targetNamespace="urn:enterprise.soap.sforce.com">
                    <!-- Query Operations -->
                    <element name="query">
                        <complexType>
                            <sequence>
                                <element name="queryString" type="xsd:string"/>
                            </sequence>
                        </complexType>
                    </element>
                    <element name="queryResponse">
                        <complexType>
                            <sequence>
                                <element name="result" type="tns:QueryResult"/>
                            </sequence>
                        </complexType>
                    </element>
                    <complexType name="QueryResult">
                        <sequence>
                            <element name="done" type="xsd:boolean"/>
                            <element name="queryLocator" type="xsd:string" nillable="true"/>
                            <element name="records" type="tns:sObject" minOccurs="0" maxOccurs="unbounded"/>
                            <element name="size" type="xsd:int"/>
                        </sequence>
                    </complexType>
                    
                    <!-- queryMore operation -->
                    <element name="queryMore">
                        <complexType>
                            <sequence>
                                <element name="queryLocator" type="xsd:string"/>
                            </sequence>
                        </complexType>
                    </element>
                    <element name="queryMoreResponse">
                        <complexType>
                            <sequence>
                                <element name="result" type="tns:QueryResult"/>
                            </sequence>
                        </complexType>
                    </element>
                    
                    <!-- create operation -->
                    <element name="create">
                        <complexType>
                            <sequence>
                                <element name="sObjects" type="tns:sObject" minOccurs="0" maxOccurs="unbounded"/>
                            </sequence>
                        </complexType>
                    </element>
                    <element name="createResponse">
                        <complexType>
                            <sequence>
                                <element name="result" type="tns:SaveResult" minOccurs="0" maxOccurs="unbounded"/>
                            </sequence>
                        </complexType>
                    </element>
                    <complexType name="SaveResult">
                        <sequence>
                            <element name="id" type="tns:ID" nillable="true"/>
                            <element name="success" type="xsd:boolean"/>
                            <element name="errors" minOccurs="0" maxOccurs="unbounded" type="tns:Error"/>
                        </sequence>
                    </complexType>
                    <complexType name="Error">
                        <sequence>
                            <element name="fields" minOccurs="0" maxOccurs="unbounded" type="xsd:string"/>
                            <element name="message" type="xsd:string"/>
                            <element name="statusCode" type="tns:StatusCode"/>
                        </sequence>
                    </complexType>
                    <simpleType name="StatusCode">
                        <restriction base="xsd:string">
                            <enumeration value="INVALID_FIELD"/>
                            <enumeration value="REQUIRED_FIELD_MISSING"/>
                            <enumeration value="ALL_OR_NONE_OPERATION_ROLLED_BACK"/>
                        </restriction>
                    </simpleType>
                    
                    <!-- describeSObject operation -->
                    <element name="describeSObject">
                        <complexType>
                            <sequence>
                                <element name="sObjectType" type="xsd:string"/>
                            </sequence>
                        </complexType>
                    </element>
                    <element name="describeSObjectResponse">
                        <complexType>
                            <sequence>
                                <element name="result" type="tns:DescribeSObjectResult"/>
                            </sequence>
                        </complexType>
                    </element>
                    <complexType name="DescribeSObjectResult">
                        <sequence>
                            <element name="activateable" type="xsd:boolean"/>
                            <element name="createable" type="xsd:boolean"/>
                            <element name="custom" type="xsd:boolean"/>
                            <element name="deletable" type="xsd:boolean"/>
                            <element name="fields" minOccurs="0" maxOccurs="unbounded" type="tns:Field"/>
                            <element name="label" type="xsd:string"/>
                            <element name="name" type="xsd:string"/>
                            <element name="updateable" type="xsd:boolean"/>
                        </sequence>
                    </complexType>
                    <complexType name="Field">
                        <sequence>
                            <element name="createable" type="xsd:boolean"/>
                            <element name="custom" type="xsd:boolean"/>
                            <element name="defaultValue" type="xsd:string" nillable="true"/>
                            <element name="defaultedOnCreate" type="xsd:boolean"/>
                            <element name="label" type="xsd:string"/>
                            <element name="length" type="xsd:int" nillable="true"/>
                            <element name="name" type="xsd:string"/>
                            <element name="nillable" type="xsd:boolean"/>
                            <element name="precision" type="xsd:int" nillable="true"/>
                            <element name="scale" type="xsd:int" nillable="true"/>
                            <element name="type" type="xsd:string"/>
                            <element name="unique" type="xsd:boolean"/>
                            <element name="updateable" type="xsd:boolean"/>
                            <element name="referenceTo" type="xsd:string" nillable="true" minOccurs="0" maxOccurs="unbounded"/>
                            <element name="relationshipName" type="xsd:string" nillable="true"/>
                            <element name="picklistValues" type="tns:PicklistEntry" minOccurs="0" maxOccurs="unbounded"/>
                        </sequence>
                    </complexType>
                    <complexType name="PicklistEntry">
                        <sequence>
                            <element name="active" type="xsd:boolean"/>
                            <element name="value" type="xsd:string"/>
                        </sequence>
                    </complexType>
                    
                    <!-- getUserInfo operation -->
                    <element name="getUserInfo">
                        <complexType>
                            <sequence>
                                <!-- Empty request -->
                            </sequence>
                        </complexType>
                    </element>
                    <element name="getUserInfoResponse">
                        <complexType>
                            <sequence>
                                <element name="result" type="tns:GetUserInfoResult"/>
                            </sequence>
                        </complexType>
                    </element>
                    <complexType name="GetUserInfoResult">
                        <sequence>
                            <element name="userId" type="xsd:string"/>
                            <element name="organizationId" type="xsd:string"/>
                            <element name="userName" type="xsd:string"/>
                            <element name="userEmail" type="xsd:string"/>
                            <element name="userFullName" type="xsd:string"/>
                            <element name="userLanguage" type="xsd:string"/>
                            <element name="userLocale" type="xsd:string"/>
                            <element name="userTimeZone" type="xsd:string"/>
                        </sequence>
                    </complexType>
                    
                    <!-- Base sObject type -->
                    <complexType name="sObject">
                        <sequence>
                            <element name="type" type="xsd:string"/>
                            <element name="fieldsToNull" minOccurs="0" maxOccurs="unbounded" type="xsd:string"/>
                            <element name="Id" minOccurs="0" type="tns:ID"/>
                            <!-- Other fields will be added dynamically -->
                        </sequence>
                    </complexType>
                    <simpleType name="ID">
                        <restriction base="xsd:string">
                            <pattern value="[a-zA-Z0-9]{18}|[a-zA-Z0-9]{15}"/>
                        </restriction>
                    </simpleType>
                </schema>
            </types>
            <message name="queryRequest">
                <part name="parameters" element="tns:query"/>
            </message>
            <message name="queryResponse">
                <part name="parameters" element="tns:queryResponse"/>
            </message>
            <message name="queryMoreRequest">
                <part name="parameters" element="tns:queryMore"/>
            </message>
            <message name="queryMoreResponse">
                <part name="parameters" element="tns:queryMoreResponse"/>
            </message>
            <message name="createRequest">
                <part name="parameters" element="tns:create"/>
            </message>
            <message name="createResponse">
                <part name="parameters" element="tns:createResponse"/>
            </message>
            <message name="describeSObjectRequest">
                <part name="parameters" element="tns:describeSObject"/>
            </message>
            <message name="describeSObjectResponse">
                <part name="parameters" element="tns:describeSObjectResponse"/>
            </message>
            <message name="getUserInfoRequest">
                <part name="parameters" element="tns:getUserInfo"/>
            </message>
            <message name="getUserInfoResponse">
                <part name="parameters" element="tns:getUserInfoResponse"/>
            </message>
            <portType name="Soap">
                <operation name="query">
                    <input message="tns:queryRequest"/>
                    <output message="tns:queryResponse"/>
                </operation>
                <operation name="queryMore">
                    <input message="tns:queryMoreRequest"/>
                    <output message="tns:queryMoreResponse"/>
                </operation>
                <operation name="create">
                    <input message="tns:createRequest"/>
                    <output message="tns:createResponse"/>
                </operation>
                <operation name="describeSObject">
                    <input message="tns:describeSObjectRequest"/>
                    <output message="tns:describeSObjectResponse"/>
                </operation>
                <operation name="getUserInfo">
                    <input message="tns:getUserInfoRequest"/>
                    <output message="tns:getUserInfoResponse"/>
                </operation>
            </portType>
            <binding name="SoapBinding" type="tns:Soap">
                <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
                <operation name="query">
                    <soap:operation soapAction=""/>
                    <input><soap:body use="literal"/></input>
                    <output><soap:body use="literal"/></output>
                </operation>
                <operation name="queryMore">
                    <soap:operation soapAction=""/>
                    <input><soap:body use="literal"/></input>
                    <output><soap:body use="literal"/></output>
                </operation>
                <operation name="create">
                    <soap:operation soapAction=""/>
                    <input><soap:body use="literal"/></input>
                    <output><soap:body use="literal"/></output>
                </operation>
                <operation name="describeSObject">
                    <soap:operation soapAction=""/>
                    <input><soap:body use="literal"/></input>
                    <output><soap:body use="literal"/></output>
                </operation>
                <operation name="getUserInfo">
                    <soap:operation soapAction=""/>
                    <input><soap:body use="literal"/></input>
                    <output><soap:body use="literal"/></output>
                </operation>
            </binding>
            <service name="SforceEnterpriseService">
                <port name="Soap" binding="tns:SoapBinding">
                    <soap:address location="${self.instance_url}/services/Soap/u/58.0"/>
                </port>
            </service>
        </definitions>
        '''
        
        # Replace the placeholders with instance URL
        enterprise_wsdl_content = enterprise_wsdl_content.replace(
            '${self.instance_url}',
            self.instance_url
        )
        
        # Create a temporary file for the WSDL
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wsdl', delete=False) as temp:
            temp.write(enterprise_wsdl_content)
            temp_path = temp.name
            
        return temp_path

# Helper functions for the main application
def get_salesforce_objects_soap(instance_url, session_id):
    """
    Get list of objects from Salesforce using SOAP API
    """
    try:
        # Direct SOAP request
        endpoint = f"{instance_url}/services/Soap/u/58.0"
        
        # XML request template for SOQL query instead of describe global
        soap_request = f'''
        <?xml version="1.0" encoding="utf-8" ?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xmlns:urn="urn:partner.soap.sforce.com">
            <soapenv:Header>
                <urn:SessionHeader>
                    <urn:sessionId>{session_id}</urn:sessionId>
                </urn:SessionHeader>
            </soapenv:Header>
            <soapenv:Body>
                <urn:query>
                    <urn:queryString>SELECT QualifiedApiName, Label, IsCustomSetting FROM EntityDefinition WHERE IsQueryable = true ORDER BY Label</urn:queryString>
                </urn:query>
            </soapenv:Body>
        </soapenv:Envelope>
        '''.strip()
        
        headers = {
            'Content-Type': 'text/xml; charset=UTF-8',
            'SOAPAction': '""'
        }
        
        response = requests.post(endpoint, data=soap_request, headers=headers)
        
        # Check for errors
        if response.status_code != 200:
            error_message = f"SOAP query failed with status {response.status_code}: {response.text}"
            logger.error(error_message)
            raise Exception(error_message)
        
        # Parse XML response manually
        import xml.etree.ElementTree as ET
        # Add namespace prefix mapping
        namespaces = {
            'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
            'partner': 'urn:partner.soap.sforce.com'
        }
        
        root = ET.fromstring(response.content)
        
        # Find all records in the query result
        result = root.find('.//partner:queryResponse/partner:result', namespaces)
        
        if result is None:
            raise Exception("Could not find query result in SOAP response")
            
        # Extract records
        records = result.findall('./partner:records', namespaces)
        
        objects = []
        for record in records:
            api_name = record.find('./partner:QualifiedApiName', namespaces)
            label = record.find('./partner:Label', namespaces)
            
            if api_name is not None and label is not None:
                objects.append({
                    'name': api_name.text,
                    'label': label.text,
                    'custom': api_name.text is not None and api_name.text.endswith('__c')
                })
        
        return objects
        
    except Exception as e:
        logger.error(f"Error getting objects via SOAP: {str(e)}")
        raise Exception(f"SOAP API error: {str(e)}")

def get_object_describe_soap(instance_url, session_id, object_name):
    """
    Get full describe information for an object using SOAP API
    """
    try:
        # Direct SOAP request
        endpoint = f"{instance_url}/services/Soap/u/58.0"
        
        # XML request template for describeSObject
        soap_request = f'''
        <?xml version="1.0" encoding="utf-8" ?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xmlns:urn="urn:partner.soap.sforce.com">
            <soapenv:Header>
                <urn:SessionHeader>
                    <urn:sessionId>{session_id}</urn:sessionId>
                </urn:SessionHeader>
            </soapenv:Header>
            <soapenv:Body>
                <urn:describeSObject>
                    <urn:sObjectType>{object_name}</urn:sObjectType>
                </urn:describeSObject>
            </soapenv:Body>
        </soapenv:Envelope>
        '''.strip()
        
        headers = {
            'Content-Type': 'text/xml; charset=UTF-8',
            'SOAPAction': '""'
        }
        
        response = requests.post(endpoint, data=soap_request, headers=headers)
        
        # Check for errors
        if response.status_code != 200:
            error_message = f"SOAP describeSObject failed with status {response.status_code}: {response.text}"
            logger.error(error_message)
            raise Exception(error_message)
        
        # Parse XML response manually
        import xml.etree.ElementTree as ET
        # Add namespace prefix mapping
        namespaces = {
            'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
            'partner': 'urn:partner.soap.sforce.com'
        }
        
        root = ET.fromstring(response.content)
        
        # Find the result element
        result = root.find('.//partner:describeSObjectResponse/partner:result', namespaces)
        
        if result is None:
            raise Exception("Could not find describeSObject result in SOAP response")
            
        # Extract basic object info
        name = result.find('./partner:name', namespaces)
        label = result.find('./partner:label', namespaces)
        
        object_info = {
            'name': name.text if name is not None else object_name,
            'label': label.text if label is not None else object_name,
            'fields': []
        }
        
        # Extract fields
        fields = result.findall('./partner:fields', namespaces)
        
        for field in fields:
            field_name = field.find('./partner:name', namespaces)
            field_label = field.find('./partner:label', namespaces)
            field_type = field.find('./partner:type', namespaces)
            field_nillable = field.find('./partner:nillable', namespaces)
            field_defaultedOnCreate = field.find('./partner:defaultedOnCreate', namespaces)
            field_unique = field.find('./partner:unique', namespaces)
            field_custom = field.find('./partner:custom', namespaces)
            field_updatable = field.find('./partner:updateable', namespaces)
            field_defaultValue = field.find('./partner:defaultValue', namespaces)
            
            if field_name is not None:
                field_info = {
                    'name': field_name.text,
                    'label': field_label.text if field_label is not None else field_name.text,
                    'type': field_type.text if field_type is not None else 'string',
                    'required': (field_nillable is not None and field_nillable.text is not None and field_nillable.text.lower() == 'false' and 
                                field_defaultedOnCreate is not None and field_defaultedOnCreate.text is not None and field_defaultedOnCreate.text.lower() == 'false'),
                    'unique': field_unique is not None and field_unique.text is not None and field_unique.text.lower() == 'true',
                    'custom': field_custom is not None and field_custom.text is not None and field_custom.text.lower() == 'true',
                    'updateable': field_updatable is not None and field_updatable.text is not None and field_updatable.text.lower() == 'true',
                    'defaultValue': field_defaultValue.text if field_defaultValue is not None else None
                }
                
                # Get relationship info if it's a reference field
                if field_type is not None and field_type.text == 'reference':
                    relationshipName = field.find('./partner:relationshipName', namespaces)
                    referenceTo = field.findall('./partner:referenceTo', namespaces)
                    
                    if relationshipName is not None:
                        field_info['relationshipName'] = relationshipName.text
                    
                    if referenceTo:
                        field_info['referenceTo'] = [ref.text for ref in referenceTo if ref.text]
                
                # Get picklist values if applicable
                if field_type is not None and field_type.text in ('picklist', 'multipicklist'):
                    picklistValues = field.findall('./partner:picklistValues', namespaces)
                    field_info['picklistValues'] = []
                    
                    for pv in picklistValues:
                        value = pv.find('./partner:value', namespaces)
                        active = pv.find('./partner:active', namespaces)
                        
                        if value is not None and active is not None and active.text is not None and active.text.lower() == 'true':
                            field_info['picklistValues'].append(value.text)
                
                # Add length for string fields
                if field_type is not None and field_type.text in ('string', 'textarea'):
                    length = field.find('./partner:length', namespaces)
                    if length is not None:
                        field_info['length'] = int(length.text)
                
                # Add precision and scale for numeric fields
                if field_type is not None and field_type.text in ('double', 'currency', 'percent'):
                    precision = field.find('./partner:precision', namespaces)
                    scale = field.find('./partner:scale', namespaces)
                    
                    if precision is not None:
                        field_info['precision'] = int(precision.text)
                    if scale is not None:
                        field_info['scale'] = int(scale.text)
                
                object_info['fields'].append(field_info)
        
        return object_info
        
    except Exception as e:
        logger.error(f"Error getting object describe via SOAP: {str(e)}")
        raise Exception(f"SOAP describeSObject error: {str(e)}")
    
def insert_records_soap(instance_url, session_id, object_name, records):
    """
    Insert multiple records using SOAP API
    """
    try:
        results = []
        
        # Process each record with a separate create request
        for record in records:
            # Direct SOAP request
            endpoint = f"{instance_url}/services/Soap/u/58.0"
            
            # Build field XML
            fields_xml = ''
            for field, value in record.items():
                # Skip None values
                if value is None:
                    continue
                    
                # Format value based on type
                if isinstance(value, bool):
                    formatted_value = str(value).lower()
                elif isinstance(value, (int, float)):
                    formatted_value = str(value)
                else:
                    # Escape XML special characters
                    if value is None:
                        formatted_value = ''
                    else:
                        formatted_value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace('\'', '&apos;')
                    
                fields_xml += f"<{field}>{formatted_value}</{field}>\n"
            
            # XML request template for create
            soap_request = f'''
            <?xml version="1.0" encoding="utf-8" ?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                           xmlns:urn="urn:partner.soap.sforce.com"
                           xmlns:urn1="urn:sobject.partner.soap.sforce.com">
                <soapenv:Header>
                    <urn:SessionHeader>
                        <urn:sessionId>{session_id}</urn:sessionId>
                    </urn:SessionHeader>
                </soapenv:Header>
                <soapenv:Body>
                    <urn:create>
                        <urn:sObjects xsi:type="urn1:{object_name}">
                            {fields_xml}
                        </urn:sObjects>
                    </urn:create>
                </soapenv:Body>
            </soapenv:Envelope>
            '''.strip()
            
            headers = {
                'Content-Type': 'text/xml; charset=UTF-8',
                'SOAPAction': '""'
            }
            
            response = requests.post(endpoint, data=soap_request, headers=headers)
            
            # Process response
            if response.status_code != 200:
                error_message = f"SOAP create failed with status {response.status_code}: {response.text}"
                logger.error(error_message)
                results.append({
                    'success': False,
                    'errors': [error_message]
                })
                continue
                
            # Parse XML response manually
            import xml.etree.ElementTree as ET
            # Add namespace prefix mapping
            namespaces = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'partner': 'urn:partner.soap.sforce.com'
            }
            
            root = ET.fromstring(response.content)
            
            # Check for success
            result_elem = root.find('.//partner:createResponse/partner:result', namespaces)
            
            if result_elem is None:
                results.append({
                    'success': False,
                    'errors': ['Could not find create result in SOAP response']
                })
                continue
                
            success_elem = result_elem.find('./partner:success', namespaces)
            
            if success_elem is not None and success_elem.text is not None and success_elem.text.lower() == 'true':
                # Success - get the ID
                id_elem = result_elem.find('./partner:id', namespaces)
                
                results.append({
                    'success': True,
                    'id': id_elem.text if id_elem is not None else None
                })
            else:
                # Error - get error details
                errors = []
                error_elems = result_elem.findall('./partner:errors', namespaces)
                
                for error in error_elems:
                    message = error.find('./partner:message', namespaces)
                    if message is not None:
                        errors.append(message.text)
                    
                results.append({
                    'success': False,
                    'errors': errors if errors else ['Unknown error during record creation']
                })
        
        return results
        
    except Exception as e:
        logger.error(f"Error creating records via SOAP: {str(e)}")
        raise Exception(f"SOAP create error: {str(e)}")

def login_with_username_password(username, password, security_token=None):
    """
    Login to Salesforce using username and password via SOAP API
    """
    soap_client = SalesforceSOAPClient(username=username, password=password, security_token=security_token)
    soap_client.login_with_soap()
    
    # Get user info to confirm login was successful
    user_info = soap_client.get_user_info()
    
    return {
        'access_token': soap_client.session_id,
        'instance_url': soap_client.instance_url,
        'user_info': user_info
    }

import os
import logging
import requests
import tempfile
import base64

# Try to import zeep, but allow the module to run without it for error handling purposes
try:
    from zeep import Client
    from zeep.transports import Transport
    from zeep.cache import SqliteCache
    from zeep.exceptions import Fault
    HAS_ZEEP = True
except ImportError:
    HAS_ZEEP = False
    # Create placeholder classes for type hints
    class Client: pass
    class Transport: pass
    class SqliteCache: pass
    class Fault(Exception): pass
import tempfile
import base64

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
ENTERPRISE_WSDL_URL = "https://yourInstance.salesforce.com/soap/wsdl.jsp?type=enterprise"

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
            
        # Create a temporary file for the login WSDL
        login_wsdl = self._get_login_wsdl()
        transport = Transport(cache=SqliteCache())
        
        try:
            client = Client(login_wsdl, transport=transport)
            password_with_token = f"{self.password}{self.security_token or ''}"            
            result = client.service.login(self.username, password_with_token)
            
            self.session_id = result.sessionId
            server_url = result.serverUrl
            self.instance_url = server_url.split('/services/')[0]
            
            self.headers = {
                'SessionId': self.session_id,
                'Content-Type': 'text/xml;charset=UTF-8',
                'SOAPAction': '""'
            }
            
            logger.debug(f"Successfully logged in via SOAP API. Instance URL: {self.instance_url}")
            return True
            
        except Fault as e:
            logger.error(f"SOAP login fault: {str(e)}")
            raise Exception(f"Failed to login via SOAP: {str(e)}")
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
            # Get and parse the Enterprise WSDL
            enterprise_wsdl = self._get_enterprise_wsdl()
            transport = Transport(cache=SqliteCache())
            transport.session.headers = self.headers
            
            client = Client(enterprise_wsdl, transport=transport)
            result = client.service.getUserInfo()
            
            return {
                'user_id': result.userId,
                'org_id': result.organizationId,
                'username': result.userName,
                'email': result.userEmail,
                'full_name': f"{result.userFullName}",
                'language': result.userLanguage,
                'locale': result.userLocale,
                'timezone': result.userTimeZone,
            }
            
        except Fault as e:
            logger.error(f"SOAP getUserInfo fault: {str(e)}")
            raise Exception(f"Failed to get user info via SOAP: {str(e)}")
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
            # Get and parse the Enterprise WSDL
            enterprise_wsdl = self._get_enterprise_wsdl()
            transport = Transport(cache=SqliteCache())
            transport.session.headers = self.headers
            
            client = Client(enterprise_wsdl, transport=transport)
            result = client.service.query(soql_query)
            
            records = []
            if hasattr(result, 'records'):
                records = result.records
                
                # Handle pagination if needed
                while not result.done:
                    result = client.service.queryMore(result.queryLocator)
                    if hasattr(result, 'records'):
                        records.extend(result.records)
            
            return records
            
        except Fault as e:
            logger.error(f"SOAP query fault: {str(e)}")
            raise Exception(f"Failed to execute query via SOAP: {str(e)}")
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
            # Get and parse the Enterprise WSDL
            enterprise_wsdl = self._get_enterprise_wsdl()
            transport = Transport(cache=SqliteCache())
            transport.session.headers = self.headers
            
            client = Client(enterprise_wsdl, transport=transport)
            result = client.service.describeSObject(object_name)
            
            # Convert to a simplified Python dict structure
            object_info = {
                'name': result.name,
                'label': result.label,
                'fields': [],
                'relationships': []
            }
            
            # Process fields
            for field in result.fields:
                field_info = {
                    'name': field.name,
                    'label': field.label,
                    'type': field.type,
                    'required': not field.nillable and not field.defaultedOnCreate,
                    'unique': field.unique,
                    'custom': field.custom,
                    'updateable': field.updateable,
                    'defaultValue': field.defaultValue
                }
                
                # Add reference information if it's a lookup/master-detail
                if field.type in ('reference'):
                    field_info['referenceTo'] = field.referenceTo
                    field_info['relationshipName'] = field.relationshipName
                
                # Add picklist values if applicable
                if field.type in ('picklist', 'multipicklist'):
                    field_info['picklistValues'] = [
                        pv.value for pv in field.picklistValues 
                        if pv.active
                    ]
                    
                # Add length for string fields
                if field.type in ('string', 'textarea'):
                    field_info['length'] = field.length
                    
                # Add precision and scale for numeric fields
                if field.type in ('double', 'currency', 'percent'):
                    field_info['precision'] = field.precision
                    field_info['scale'] = field.scale
                
                object_info['fields'].append(field_info)
            
            return object_info
            
        except Fault as e:
            logger.error(f"SOAP describeSObject fault: {str(e)}")
            raise Exception(f"Failed to describe object via SOAP: {str(e)}")
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
            # Get and parse the Enterprise WSDL
            enterprise_wsdl = self._get_enterprise_wsdl()
            transport = Transport(cache=SqliteCache())
            transport.session.headers = self.headers
            
            client = Client(enterprise_wsdl, transport=transport)
            
            # Create the sObject
            sobject = client.factory.create(f'ns0:{sobject_type}')
            
            # Set field values
            for field, value in sobject_data.items():
                setattr(sobject, field, value)
            
            # Create the record
            result = client.service.create(sobject)
            
            if result.success:
                return {
                    'id': result.id,
                    'success': True
                }
            else:
                errors = [error for error in result.errors]
                return {
                    'success': False,
                    'errors': errors
                }
                
        except Fault as e:
            logger.error(f"SOAP create fault: {str(e)}")
            raise Exception(f"Failed to create record via SOAP: {str(e)}")
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
            # Get and parse the Enterprise WSDL
            enterprise_wsdl = self._get_enterprise_wsdl()
            transport = Transport(cache=SqliteCache())
            transport.session.headers = self.headers
            
            client = Client(enterprise_wsdl, transport=transport)
            
            # Create the sObjects
            sobjects = []
            for record_data in records:
                sobject = client.factory.create(f'ns0:{sobject_type}')
                for field, value in record_data.items():
                    setattr(sobject, field, value)
                sobjects.append(sobject)
            
            # Create the records
            results = client.service.create(sobjects)
            
            # Process results
            processed_results = {
                'success': 0,
                'failure': 0,
                'errors': [],
                'created_ids': []
            }
            
            for result in results:
                if result.success:
                    processed_results['success'] += 1
                    processed_results['created_ids'].append(result.id)
                else:
                    processed_results['failure'] += 1
                    for error in result.errors:
                        processed_results['errors'].append({
                            'message': error.message,
                            'fields': error.fields,
                            'statusCode': error.statusCode
                        })
            
            return processed_results
                
        except Fault as e:
            logger.error(f"SOAP create_multiple fault: {str(e)}")
            raise Exception(f"Failed to create multiple records via SOAP: {str(e)}")
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
                    <element name="currencySymbol" type="xsd:string" nillable="true"/>
                    <element name="orgAttachmentFileSizeLimit" type="xsd:int"/>
                    <element name="orgDefaultCurrencyIsoCode" type="xsd:string" nillable="true"/>
                    <element name="orgDisallowHtmlAttachments" type="xsd:boolean"/>
                    <element name="orgHasPersonAccounts" type="xsd:boolean"/>
                    <element name="organizationId" type="xsd:string"/>
                    <element name="organizationMultiCurrency" type="xsd:boolean"/>
                    <element name="organizationName" type="xsd:string"/>
                    <element name="profileId" type="xsd:string"/>
                    <element name="roleId" type="xsd:string" nillable="true"/>
                    <element name="userDefaultCurrencyIsoCode" type="xsd:string" nillable="true"/>
                    <element name="userEmail" type="xsd:string"/>
                    <element name="userFullName" type="xsd:string"/>
                    <element name="userId" type="xsd:string"/>
                    <element name="userLanguage" type="xsd:string"/>
                    <element name="userLocale" type="xsd:string"/>
                    <element name="userName" type="xsd:string"/>
                    <element name="userTimeZone" type="xsd:string"/>
                    <element name="userType" type="xsd:string"/>
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
                    <soap:address location="https://yourInstance.salesforce.com/services/Soap/c/58.0/ORGID"/>
                </port>
            </service>
        </definitions>
        '''
        
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
    soap_client = SalesforceSOAPClient()
    soap_client.login_with_oauth_token(session_id, instance_url)
    
    # Query for object info using a SOQL query
    soql = "SELECT QualifiedApiName, Label, IsCustomSetting, IsCustomizable FROM EntityDefinition WHERE IsQueryable = true ORDER BY Label"
    records = soap_client.query(soql)
    
    # Filter objects to only include those we want to show
    objects = []
    for record in records:
        if hasattr(record, 'IsCustomizable') and record.IsCustomizable:
            objects.append({
                'name': record.QualifiedApiName,
                'label': record.Label,
                'custom': record.QualifiedApiName.endswith('__c')
            })
    
    return objects

def get_object_describe_soap(instance_url, session_id, object_name):
    """
    Get full describe information for an object using SOAP API
    """
    soap_client = SalesforceSOAPClient()
    soap_client.login_with_oauth_token(session_id, instance_url)
    
    # Get object metadata
    object_info = soap_client.describe_sobject(object_name)
    return object_info
    
def insert_records_soap(instance_url, session_id, object_name, records):
    """
    Insert multiple records using SOAP API
    """
    soap_client = SalesforceSOAPClient()
    soap_client.login_with_oauth_token(session_id, instance_url)
    
    # Insert records
    results = soap_client.create_multiple(object_name, records)
    return results

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

"""
Unit tests for salesforce_soap_utils.py
"""
import json
import unittest
import pytest
from unittest.mock import patch, MagicMock, Mock
from salesforce_soap_utils import (
    SalesforceSOAPClient,
    get_salesforce_objects_soap,
    get_object_describe_soap,
    insert_records_soap,
    login_with_username_password
)

class TestSalesforceSOAPUtils(unittest.TestCase):
    """Test the Salesforce SOAP API utility functions"""
    
    def setUp(self):
        """Setup test data"""
        # Test credentials
        self.username = 'test@example.com'
        self.password = 'password123'
        self.security_token = 'SECURITY_TOKEN'
        
        # Mock session information
        self.session_id = 'MOCK_SESSION_ID'
        self.instance_url = 'https://test.salesforce.com'
        
        # Sample test data
        self.test_records = [
            {'Name': 'Test Record 1', 'Industry': 'Technology'},
            {'Name': 'Test Record 2', 'Industry': 'Healthcare'}
        ]
        
        # Sample object metadata
        self.account_describe = {
            'name': 'Account',
            'label': 'Account',
            'fields': [
                {
                    'name': 'Name',
                    'label': 'Account Name',
                    'type': 'string',
                    'length': 80,
                    'createable': True,
                    'updateable': True
                },
                {
                    'name': 'Industry',
                    'label': 'Industry',
                    'type': 'picklist',
                    'createable': True,
                    'updateable': True,
                    'picklistValues': [
                        {'value': 'Technology', 'active': True},
                        {'value': 'Healthcare', 'active': True},
                        {'value': 'Finance', 'active': True}
                    ]
                }
            ]
        }
        
        # Sample objects list
        self.sf_objects = [
            {'name': 'Account', 'label': 'Account', 'keyPrefix': '001'},
            {'name': 'Contact', 'label': 'Contact', 'keyPrefix': '003'},
            {'name': 'Opportunity', 'label': 'Opportunity', 'keyPrefix': '006'},
            {'name': 'CustomObject__c', 'label': 'Custom Object', 'keyPrefix': 'a00'}
        ]

    @patch('salesforce_soap_utils.Client')
    def test_soap_client_init(self, mock_client):
        """Test initializing a SOAP client"""
        # Create a SOAP client
        client = SalesforceSOAPClient(
            username=self.username,
            password=self.password,
            security_token=self.security_token
        )
        
        # Verify client attributes
        self.assertEqual(client.username, self.username)
        self.assertEqual(client.password, self.password)
        self.assertEqual(client.security_token, self.security_token)
        self.assertIsNone(client.session_id)
        self.assertIsNone(client.instance_url)
        self.assertIsNone(client.soap_client)

    @patch('salesforce_soap_utils.Client')
    def test_login_with_soap(self, mock_client):
        """Test SOAP login with username/password"""
        # Setup mock response
        mock_login_result = MagicMock()
        mock_login_result.sessionId = self.session_id
        mock_login_result.serverUrl = f"{self.instance_url}/services/Soap/c/55.0/00D00000000001"
        
        mock_client_instance = MagicMock()
        mock_client_instance.service.login.return_value = mock_login_result
        mock_client.return_value = mock_client_instance
        
        # Create and login with SOAP client
        client = SalesforceSOAPClient(
            username=self.username,
            password=self.password,
            security_token=self.security_token
        )
        client.login_with_soap()
        
        # Verify login was called with correct credentials
        mock_client_instance.service.login.assert_called_once_with(
            self.username, f"{self.password}{self.security_token}"
        )
        
        # Verify client attributes are updated
        self.assertEqual(client.session_id, self.session_id)
        self.assertEqual(client.instance_url, self.instance_url)
        self.assertIsNotNone(client.soap_client)

    @patch('salesforce_soap_utils.Client')
    def test_login_with_oauth_token(self, mock_client):
        """Test initializing SOAP client with OAuth token"""
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        # Create client
        client = SalesforceSOAPClient()
        client.login_with_oauth_token(self.session_id, self.instance_url)
        
        # Verify client attributes are set
        self.assertEqual(client.session_id, self.session_id)
        self.assertEqual(client.instance_url, self.instance_url)
        self.assertIsNotNone(client.soap_client)
        
        # Verify header is set with session id
        expected_header = {'SessionHeader': {'sessionId': self.session_id}}
        self.assertEqual(mock_client_instance.set_options.call_args[1]['soapheaders'], expected_header)

    @patch('salesforce_soap_utils.Client')
    def test_query(self, mock_client):
        """Test executing a SOQL query"""
        # Setup mock response
        mock_query_result = MagicMock()
        mock_query_result.size = 2
        
        mock_record1 = MagicMock()
        mock_record1.Id = '001000000001AAA'
        mock_record1.Name = 'Test Account 1'
        
        mock_record2 = MagicMock()
        mock_record2.Id = '001000000002AAA'
        mock_record2.Name = 'Test Account 2'
        
        mock_query_result.records = [mock_record1, mock_record2]
        mock_query_result.done = True
        
        # Configure mock client
        mock_client_instance = MagicMock()
        mock_client_instance.service.query.return_value = mock_query_result
        mock_client.return_value = mock_client_instance
        
        # Create client and log in
        client = SalesforceSOAPClient()
        client.login_with_oauth_token(self.session_id, self.instance_url)
        
        # Execute query
        query = "SELECT Id, Name FROM Account LIMIT 10"
        result = client.query(query)
        
        # Verify query was called
        mock_client_instance.service.query.assert_called_once_with(query)
        
        # Verify result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['Id'], '001000000001AAA')
        self.assertEqual(result[0]['Name'], 'Test Account 1')
        self.assertEqual(result[1]['Id'], '001000000002AAA')
        self.assertEqual(result[1]['Name'], 'Test Account 2')

    @patch('salesforce_soap_utils.Client')
    def test_describe_sobject(self, mock_client):
        """Test describing a Salesforce object"""
        # Setup mock response
        mock_describe_result = MagicMock()
        mock_describe_result.name = 'Account'
        mock_describe_result.label = 'Account'
        mock_describe_result.keyPrefix = '001'
        
        # Create mock field
        mock_field1 = MagicMock()
        mock_field1.name = 'Name'
        mock_field1.label = 'Account Name'
        mock_field1.type = 'string'
        mock_field1.length = 80
        mock_field1.createable = True
        
        mock_field2 = MagicMock()
        mock_field2.name = 'Industry'
        mock_field2.label = 'Industry'
        mock_field2.type = 'picklist'
        mock_field2.createable = True
        
        # Setup picklist values
        mock_picklist_value = MagicMock()
        mock_picklist_value.value = 'Technology'
        mock_picklist_value.active = True
        mock_field2.picklistValues = [mock_picklist_value]
        
        mock_describe_result.fields = [mock_field1, mock_field2]
        
        # Configure mock client
        mock_client_instance = MagicMock()
        mock_client_instance.service.describeSObject.return_value = mock_describe_result
        mock_client.return_value = mock_client_instance
        
        # Create client and log in
        client = SalesforceSOAPClient()
        client.login_with_oauth_token(self.session_id, self.instance_url)
        
        # Describe object
        object_name = 'Account'
        result = client.describe_sobject(object_name)
        
        # Verify describeSObject was called
        mock_client_instance.service.describeSObject.assert_called_once_with(object_name)
        
        # Verify result
        self.assertEqual(result['name'], 'Account')
        self.assertEqual(result['label'], 'Account')
        self.assertEqual(len(result['fields']), 2)
        self.assertEqual(result['fields'][0]['name'], 'Name')
        self.assertEqual(result['fields'][1]['name'], 'Industry')
        self.assertEqual(result['fields'][1]['type'], 'picklist')
        self.assertEqual(result['fields'][1]['picklistValues'][0]['value'], 'Technology')

    @patch('salesforce_soap_utils.Client')
    def test_create(self, mock_client):
        """Test creating a single record"""
        # Setup mock response
        mock_create_result = MagicMock()
        mock_create_result.success = True
        mock_create_result.id = '001000000001AAA'
        
        # Configure mock client
        mock_client_instance = MagicMock()
        mock_client_instance.service.create.return_value = [mock_create_result]
        mock_client.return_value = mock_client_instance
        
        # Create client and log in
        client = SalesforceSOAPClient()
        client.login_with_oauth_token(self.session_id, self.instance_url)
        
        # Create record
        object_type = 'Account'
        record_data = {'Name': 'Test Account'}
        result = client.create(object_type, record_data)
        
        # Verify create was called
        self.assertTrue(mock_client_instance.service.create.called)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['id'], '001000000001AAA')

    @patch('salesforce_soap_utils.Client')
    def test_create_multiple(self, mock_client):
        """Test creating multiple records"""
        # Setup mock responses
        mock_create_result1 = MagicMock()
        mock_create_result1.success = True
        mock_create_result1.id = '001000000001AAA'
        
        mock_create_result2 = MagicMock()
        mock_create_result2.success = True
        mock_create_result2.id = '001000000002AAA'
        
        # Configure mock client
        mock_client_instance = MagicMock()
        mock_client_instance.service.create.return_value = [mock_create_result1, mock_create_result2]
        mock_client.return_value = mock_client_instance
        
        # Create client and log in
        client = SalesforceSOAPClient()
        client.login_with_oauth_token(self.session_id, self.instance_url)
        
        # Create records
        object_type = 'Account'
        records = [
            {'Name': 'Test Account 1'},
            {'Name': 'Test Account 2'}
        ]
        results = client.create_multiple(object_type, records)
        
        # Verify create was called
        self.assertTrue(mock_client_instance.service.create.called)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]['success'])
        self.assertEqual(results[0]['id'], '001000000001AAA')
        self.assertTrue(results[1]['success'])
        self.assertEqual(results[1]['id'], '001000000002AAA')

    @patch('salesforce_soap_utils.SalesforceSOAPClient')
    def test_get_salesforce_objects_soap(self, mock_client_class):
        """Test getting Salesforce objects via SOAP API"""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock global describe response
        mock_client.query.return_value = [
            {'Name': 'Account', 'Label': 'Account', 'KeyPrefix': '001'},
            {'Name': 'Contact', 'Label': 'Contact', 'KeyPrefix': '003'}
        ]
        
        # Get objects
        result = get_salesforce_objects_soap(self.instance_url, self.session_id)
        
        # Verify client was initialized with oauth token
        mock_client.login_with_oauth_token.assert_called_once_with(
            self.session_id, self.instance_url
        )
        
        # Verify result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'Account')
        self.assertEqual(result[1]['name'], 'Contact')

    @patch('salesforce_soap_utils.SalesforceSOAPClient')
    def test_get_object_describe_soap(self, mock_client_class):
        """Test getting object describe via SOAP API"""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock describe response
        mock_client.describe_sobject.return_value = self.account_describe
        
        # Get describe
        object_name = 'Account'
        result = get_object_describe_soap(self.instance_url, self.session_id, object_name)
        
        # Verify client was initialized with oauth token
        mock_client.login_with_oauth_token.assert_called_once_with(
            self.session_id, self.instance_url
        )
        
        # Verify describe was called with correct object
        mock_client.describe_sobject.assert_called_once_with(object_name)
        
        # Verify result
        self.assertEqual(result['name'], 'Account')
        self.assertEqual(len(result['fields']), 2)

    @patch('salesforce_soap_utils.SalesforceSOAPClient')
    def test_insert_records_soap(self, mock_client_class):
        """Test inserting records via SOAP API"""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock create_multiple response
        mock_client.create_multiple.return_value = [
            {'success': True, 'id': '001000000001AAA'},
            {'success': True, 'id': '001000000002AAA'}
        ]
        
        # Insert records
        object_name = 'Account'
        result = insert_records_soap(self.instance_url, self.session_id, object_name, self.test_records)
        
        # Verify client was initialized with oauth token
        mock_client.login_with_oauth_token.assert_called_once_with(
            self.session_id, self.instance_url
        )
        
        # Verify create_multiple was called with correct parameters
        mock_client.create_multiple.assert_called_once_with(object_name, self.test_records)
        
        # Verify result
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]['success'])
        self.assertEqual(result[0]['id'], '001000000001AAA')

    @patch('salesforce_soap_utils.SalesforceSOAPClient')
    def test_login_with_username_password(self, mock_client_class):
        """Test logging in with username and password"""
        # Setup mock client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Configure login response
        mock_client.session_id = self.session_id
        mock_client.instance_url = self.instance_url
        
        # Login with username/password
        result = login_with_username_password(self.username, self.password, self.security_token)
        
        # Verify client was created with correct credentials
        mock_client_class.assert_called_once_with(
            username=self.username,
            password=self.password,
            security_token=self.security_token
        )
        
        # Verify login was called
        mock_client.login_with_soap.assert_called_once()
        
        # Verify result
        self.assertEqual(result['session_id'], self.session_id)
        self.assertEqual(result['instance_url'], self.instance_url)

    @patch('salesforce_soap_utils.Client')
    def test_get_login_wsdl(self, mock_client):
        """Test generating login WSDL"""
        # Create client
        client = SalesforceSOAPClient()
        wsdl = client._get_login_wsdl()
        
        # Verify WSDL is a non-empty string
        self.assertIsInstance(wsdl, str)
        self.assertGreater(len(wsdl), 100)
        self.assertIn('definitions', wsdl)
        self.assertIn('Salesforce.com', wsdl)

    @patch('salesforce_soap_utils.Client')
    def test_get_enterprise_wsdl(self, mock_client):
        """Test generating enterprise WSDL"""
        # Create client
        client = SalesforceSOAPClient()
        wsdl = client._get_enterprise_wsdl()
        
        # Verify WSDL is a non-empty string
        self.assertIsInstance(wsdl, str)
        self.assertGreater(len(wsdl), 100)
        self.assertIn('definitions', wsdl)
        self.assertIn('Salesforce.com', wsdl)

if __name__ == '__main__':
    unittest.main()
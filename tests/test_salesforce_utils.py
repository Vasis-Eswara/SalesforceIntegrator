"""
Unit tests for salesforce_utils.py
"""
import json
import unittest
import pytest
from unittest.mock import patch, MagicMock, mock_open
import base64
import hashlib
import requests
from salesforce_utils import (
    generate_code_verifier,
    generate_code_challenge,
    get_auth_url,
    get_access_token,
    refresh_access_token,
    make_api_request,
    get_salesforce_objects,
    get_object_fields,
    get_object_describe,
    insert_records
)

class TestSalesforceUtils(unittest.TestCase):
    """Test the Salesforce API utility functions"""
    
    def setUp(self):
        """Setup test data"""
        # Mock API details
        self.client_id = 'TEST_CLIENT_ID'
        self.client_secret = 'TEST_CLIENT_SECRET'
        self.redirect_uri = 'https://test-app.com/callback'
        self.auth_code = 'TEST_AUTH_CODE'
        self.verifier = 'TEST_VERIFIER_1234567890_abcdefghijklmnopqrstuvwxyz'
        self.challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self.verifier.encode()).digest()
        ).decode().rstrip('=')
        
        # API responses
        self.access_token_response = {
            'access_token': 'TEST_ACCESS_TOKEN',
            'refresh_token': 'TEST_REFRESH_TOKEN',
            'instance_url': 'https://test.salesforce.com',
            'id': 'https://login.salesforce.com/id/00D00000000001AAA/005000000000001AAA'
        }
        
        # Access token for testing
        self.access_token = 'TEST_ACCESS_TOKEN'
        self.refresh_token = 'TEST_REFRESH_TOKEN'
        self.instance_url = 'https://test.salesforce.com'
        
        # Sample Salesforce objects data
        self.sf_objects_response = {
            'sobjects': [
                {'name': 'Account', 'label': 'Account', 'keyPrefix': '001'},
                {'name': 'Contact', 'label': 'Contact', 'keyPrefix': '003'},
                {'name': 'Opportunity', 'label': 'Opportunity', 'keyPrefix': '006'},
                {'name': 'CustomObject__c', 'label': 'Custom Object', 'keyPrefix': 'a00'}
            ]
        }
        
        # Sample object fields data
        self.sf_fields_response = {
            'fields': [
                {
                    'name': 'Name',
                    'label': 'Account Name',
                    'type': 'string',
                    'updateable': True,
                    'createable': True
                },
                {
                    'name': 'Industry',
                    'label': 'Industry',
                    'type': 'picklist',
                    'updateable': True,
                    'createable': True,
                    'picklistValues': [
                        {'value': 'Technology', 'active': True},
                        {'value': 'Healthcare', 'active': True}
                    ]
                }
            ]
        }
        
        # Sample records to insert
        self.test_records = [
            {'Name': 'Test Account 1', 'Industry': 'Technology'},
            {'Name': 'Test Account 2', 'Industry': 'Healthcare'}
        ]
        
        # Sample insert response
        self.insert_response = {
            'compositeResponse': [
                {'httpStatusCode': 201, 'body': {'id': '001000000001AAA', 'success': True}},
                {'httpStatusCode': 201, 'body': {'id': '001000000002AAA', 'success': True}}
            ]
        }

    def test_generate_code_verifier(self):
        """Test generating a code verifier for PKCE"""
        verifier = generate_code_verifier()
        
        # Verify length and character set
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        
        # Should only contain alphanumeric, dash, underscore, period, or tilde
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~')
        for char in verifier:
            self.assertIn(char, allowed_chars)

    def test_generate_code_challenge(self):
        """Test generating a code challenge from a verifier"""
        # Use a fixed verifier for consistent testing
        verifier = 'TEST_VERIFIER_abcdefghijklmnopqrstuvwxyz_0123456789'
        challenge = generate_code_challenge(verifier)
        
        # Verify it's a base64url-encoded string
        self.assertIsInstance(challenge, str)
        
        # Calculate expected challenge for verification
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip('=')
        
        self.assertEqual(challenge, expected)

    @patch('salesforce_utils.os.environ.get')
    @patch('salesforce_utils.generate_code_verifier')
    def test_get_auth_url(self, mock_verifier, mock_env_get):
        """Test generating the Salesforce OAuth authorization URL"""
        # Setup mocks
        mock_verifier.return_value = self.verifier
        mock_env_get.side_effect = lambda key, default=None: {
            'SALESFORCE_CLIENT_ID': self.client_id,
            'SALESFORCE_REDIRECT_URI': self.redirect_uri
        }.get(key, default)
        
        # Get auth URL
        auth_url = get_auth_url()
        
        # Verify URL contains expected components
        self.assertIn('salesforce.com/services/oauth2/authorize', auth_url)
        self.assertIn(f'client_id={self.client_id}', auth_url)
        self.assertIn(f'redirect_uri={self.redirect_uri}', auth_url)
        self.assertIn('code_challenge=', auth_url)
        self.assertIn('code_challenge_method=S256', auth_url)
        self.assertIn('response_type=code', auth_url)
        
        # Verify session values would be set (need to check if mock_session was called)
        mock_env_get.assert_any_call('SALESFORCE_CLIENT_ID', '')
        mock_env_get.assert_any_call('SALESFORCE_REDIRECT_URI', '')

    @patch('salesforce_utils.os.environ.get')
    @patch('salesforce_utils.requests.post')
    @patch('salesforce_utils.session')
    def test_get_access_token(self, mock_session, mock_post, mock_env_get):
        """Test exchanging authorization code for access token"""
        # Setup mocks
        mock_post_response = MagicMock()
        mock_post_response.json.return_value = self.access_token_response
        mock_post_response.status_code = 200
        mock_post.return_value = mock_post_response
        
        mock_session.get.side_effect = lambda key, default=None: {
            'sf_code_verifier': self.verifier
        }.get(key, default)
        
        mock_env_get.side_effect = lambda key, default=None: {
            'SALESFORCE_CLIENT_ID': self.client_id,
            'SALESFORCE_CLIENT_SECRET': self.client_secret,
            'SALESFORCE_REDIRECT_URI': self.redirect_uri
        }.get(key, default)
        
        # Exchange code for token
        result = get_access_token(self.auth_code)
        
        # Verify result
        self.assertEqual(result['access_token'], 'TEST_ACCESS_TOKEN')
        self.assertEqual(result['refresh_token'], 'TEST_REFRESH_TOKEN')
        self.assertEqual(result['instance_url'], 'https://test.salesforce.com')
        
        # Verify post was called with correct parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args['data']['grant_type'], 'authorization_code')
        self.assertEqual(call_args['data']['code'], self.auth_code)
        self.assertEqual(call_args['data']['client_id'], self.client_id)
        self.assertEqual(call_args['data']['client_secret'], self.client_secret)
        self.assertEqual(call_args['data']['redirect_uri'], self.redirect_uri)
        self.assertEqual(call_args['data']['code_verifier'], self.verifier)

    @patch('salesforce_utils.os.environ.get')
    @patch('salesforce_utils.requests.post')
    def test_refresh_access_token(self, mock_post, mock_env_get):
        """Test refreshing an expired access token"""
        # Setup mocks
        mock_post_response = MagicMock()
        mock_post_response.json.return_value = {
            'access_token': 'NEW_ACCESS_TOKEN',
            'instance_url': 'https://test.salesforce.com'
        }
        mock_post_response.status_code = 200
        mock_post.return_value = mock_post_response
        
        mock_env_get.side_effect = lambda key, default=None: {
            'SALESFORCE_CLIENT_ID': self.client_id,
            'SALESFORCE_CLIENT_SECRET': self.client_secret
        }.get(key, default)
        
        # Refresh token
        result = refresh_access_token(self.refresh_token)
        
        # Verify result
        self.assertEqual(result['access_token'], 'NEW_ACCESS_TOKEN')
        self.assertEqual(result['instance_url'], 'https://test.salesforce.com')
        
        # Verify post was called with correct parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args['data']['grant_type'], 'refresh_token')
        self.assertEqual(call_args['data']['refresh_token'], self.refresh_token)
        self.assertEqual(call_args['data']['client_id'], self.client_id)
        self.assertEqual(call_args['data']['client_secret'], self.client_secret)

    @patch('salesforce_utils.requests.request')
    def test_make_api_request_get(self, mock_request):
        """Test making a GET request to Salesforce API"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True, 'result': 'data'}
        mock_request.return_value = mock_response
        
        # Make API request
        endpoint = '/services/data/v53.0/sobjects'
        result = make_api_request(self.instance_url, self.access_token, endpoint)
        
        # Verify result
        self.assertEqual(result, {'success': True, 'result': 'data'})
        
        # Verify request was called with correct parameters
        mock_request.assert_called_once()
        call_args = mock_request.call_args[1]
        self.assertEqual(call_args['method'], 'GET')
        self.assertEqual(call_args['url'], f'{self.instance_url}{endpoint}')
        self.assertEqual(call_args['headers']['Authorization'], f'Bearer {self.access_token}')

    @patch('salesforce_utils.requests.request')
    def test_make_api_request_post(self, mock_request):
        """Test making a POST request to Salesforce API"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'id': '001000000001AAA', 'success': True}
        mock_request.return_value = mock_response
        
        # Make API request
        endpoint = '/services/data/v53.0/sobjects/Account'
        data = {'Name': 'Test Account'}
        result = make_api_request(self.instance_url, self.access_token, endpoint, 'POST', data)
        
        # Verify result
        self.assertEqual(result, {'id': '001000000001AAA', 'success': True})
        
        # Verify request was called with correct parameters
        mock_request.assert_called_once()
        call_args = mock_request.call_args[1]
        self.assertEqual(call_args['method'], 'POST')
        self.assertEqual(call_args['url'], f'{self.instance_url}{endpoint}')
        self.assertEqual(call_args['headers']['Authorization'], f'Bearer {self.access_token}')
        self.assertEqual(call_args['json'], data)

    @patch('salesforce_utils.requests.request')
    def test_make_api_request_error(self, mock_request):
        """Test handling API errors"""
        # Setup mock for error response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = [
            {'errorCode': 'INVALID_FIELD', 'message': 'Invalid field: Name'}
        ]
        mock_response.text = json.dumps([
            {'errorCode': 'INVALID_FIELD', 'message': 'Invalid field: Name'}
        ])
        mock_request.return_value = mock_response
        
        # Make API request that should fail
        endpoint = '/services/data/v53.0/sobjects/Account'
        with self.assertRaises(Exception) as context:
            make_api_request(self.instance_url, self.access_token, endpoint, 'POST', {'Invalid': 'Data'})
        
        # Verify error contains Salesforce error message
        self.assertIn('INVALID_FIELD', str(context.exception))

    @patch('salesforce_utils.make_api_request')
    def test_get_salesforce_objects(self, mock_api):
        """Test getting list of Salesforce objects"""
        # Setup mock
        mock_api.return_value = self.sf_objects_response
        
        # Get objects
        result = get_salesforce_objects(self.instance_url, self.access_token)
        
        # Verify result
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]['name'], 'Account')
        self.assertEqual(result[1]['name'], 'Contact')
        self.assertEqual(result[2]['name'], 'Opportunity')
        self.assertEqual(result[3]['name'], 'CustomObject__c')
        
        # Verify API call
        mock_api.assert_called_once_with(
            self.instance_url, self.access_token, '/services/data/v53.0/sobjects'
        )

    @patch('salesforce_utils.make_api_request')
    def test_get_object_fields(self, mock_api):
        """Test getting fields for a specific object"""
        # Setup mock
        mock_api.return_value = self.sf_fields_response
        
        # Get fields
        object_name = 'Account'
        result = get_object_fields(self.instance_url, self.access_token, object_name)
        
        # Verify result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'Name')
        self.assertEqual(result[1]['name'], 'Industry')
        self.assertEqual(result[1]['type'], 'picklist')
        self.assertEqual(len(result[1]['picklistValues']), 2)
        
        # Verify API call
        mock_api.assert_called_once_with(
            self.instance_url, self.access_token, f'/services/data/v53.0/sobjects/{object_name}/describe'
        )

    @patch('salesforce_utils.make_api_request')
    def test_get_object_describe(self, mock_api):
        """Test getting full describe for an object"""
        # Setup mock
        mock_api.return_value = {
            'name': 'Account',
            'label': 'Account',
            'fields': self.sf_fields_response['fields'],
            'createable': True,
            'updateable': True,
            'deletable': True
        }
        
        # Get object describe
        object_name = 'Account'
        result = get_object_describe(self.instance_url, self.access_token, object_name)
        
        # Verify result
        self.assertEqual(result['name'], 'Account')
        self.assertEqual(result['label'], 'Account')
        self.assertEqual(len(result['fields']), 2)
        self.assertTrue(result['createable'])
        self.assertTrue(result['updateable'])
        self.assertTrue(result['deletable'])
        
        # Verify API call
        mock_api.assert_called_once_with(
            self.instance_url, self.access_token, f'/services/data/v53.0/sobjects/{object_name}/describe'
        )

    @patch('salesforce_utils.make_api_request')
    def test_insert_records(self, mock_api):
        """Test inserting multiple records"""
        # Setup mock
        mock_api.return_value = self.insert_response
        
        # Insert records
        object_name = 'Account'
        result = insert_records(self.instance_url, self.access_token, object_name, self.test_records)
        
        # Verify result
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]['success'])
        self.assertEqual(result[0]['id'], '001000000001AAA')
        self.assertTrue(result[1]['success'])
        self.assertEqual(result[1]['id'], '001000000002AAA')
        
        # Verify API call
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        
        # Endpoint should be composite/tree
        self.assertEqual(call_args[0][2], '/services/data/v53.0/composite/tree/Account')
        
        # Method should be POST
        self.assertEqual(call_args[1]['method'], 'POST')
        
        # Data should have records array
        data = call_args[1]['data']
        self.assertIn('records', data)
        self.assertEqual(len(data['records']), 2)

    @patch('salesforce_utils.requests.request')
    def test_make_api_request_malformed_response(self, mock_request):
        """Test handling malformed responses"""
        # Setup mock for non-JSON response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not a JSON response"
        mock_request.return_value = mock_response
        
        # Make API request
        endpoint = '/services/data/v53.0/sobjects'
        with self.assertRaises(Exception) as context:
            make_api_request(self.instance_url, self.access_token, endpoint)
        
        # Verify error mentions invalid response
        self.assertIn('Error parsing response', str(context.exception))

    @patch('salesforce_utils.requests.request')
    def test_make_api_request_connection_error(self, mock_request):
        """Test handling connection errors"""
        # Setup mock for connection error
        mock_request.side_effect = requests.ConnectionError("Connection failed")
        
        # Make API request
        endpoint = '/services/data/v53.0/sobjects'
        with self.assertRaises(Exception) as context:
            make_api_request(self.instance_url, self.access_token, endpoint)
        
        # Verify error contains connection information
        self.assertIn('Connection failed', str(context.exception))

if __name__ == '__main__':
    unittest.main()
"""
Unit tests for routes.py
"""
import json
import unittest
import pytest
from unittest.mock import patch, MagicMock, mock_open
import io
import os
from flask import Flask, session

# Create a patch for the app and db
with patch('app.db'):
    from models import SalesforceOrg, SalesforceCredential, GenerationJob
    import routes

class TestRoutes(unittest.TestCase):
    """Test the Flask routes"""
    
    def setUp(self):
        """Setup test environment"""
        # Create a test Flask app
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.secret_key = 'test_secret_key'
        
        # Initialize routes
        routes.init_routes(self.app)
        
        # Create a test client
        self.client = self.app.test_client()
        
        # Sample Salesforce org
        self.sf_org = MagicMock()
        self.sf_org.id = 1
        self.sf_org.instance_url = 'https://test.salesforce.com'
        self.sf_org.access_token = 'TEST_ACCESS_TOKEN'
        self.sf_org.org_id = '00D000000000001'
        self.sf_org.user_id = '005000000000001'
        
        # Sample Salesforce objects
        self.sf_objects = [
            {'name': 'Account', 'label': 'Account', 'keyPrefix': '001'},
            {'name': 'Contact', 'label': 'Contact', 'keyPrefix': '003'},
            {'name': 'Opportunity', 'label': 'Opportunity', 'keyPrefix': '006'}
        ]
        
        # Sample object schema
        self.object_schema = {
            'name': 'Account',
            'label': 'Account',
            'fields': [
                {
                    'name': 'Name',
                    'label': 'Account Name',
                    'type': 'string',
                    'length': 80,
                    'createable': True,
                    'nillable': False
                },
                {
                    'name': 'Industry',
                    'label': 'Industry',
                    'type': 'picklist',
                    'createable': True,
                    'nillable': True,
                    'picklistValues': [
                        {'value': 'Technology', 'active': True},
                        {'value': 'Healthcare', 'active': True}
                    ]
                }
            ]
        }
        
        # Sample generated data
        self.generated_data = [
            {'Name': 'Test Account 1', 'Industry': 'Technology'},
            {'Name': 'Test Account 2', 'Industry': 'Healthcare'}
        ]
        
        # Sample generation job
        self.job = MagicMock()
        self.job.id = 1
        self.job.org_id = '00D000000000001'
        self.job.object_name = 'Account'
        self.job.record_count = 2
        self.job.status = 'completed'
        self.job.raw_data = json.dumps(self.generated_data)
        self.job.results = json.dumps([
            {'id': '001000000001AAA', 'success': True},
            {'id': '001000000002AAA', 'success': True}
        ])

    @patch('routes.SalesforceOrg')
    @patch('routes.get_salesforce_objects')
    def test_index_page_logged_in(self, mock_get_objects, mock_sf_org):
        """Test index page when logged in"""
        # Setup mocks
        mock_sf_org.query.get.return_value = self.sf_org
        mock_get_objects.return_value = self.sf_objects
        
        # Setup session
        with self.client.session_transaction() as sess:
            sess['salesforce_org_id'] = 1
        
        # Make request
        response = self.client.get('/')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Connected to Salesforce', html)
        self.assertIn('https://test.salesforce.com', html)
        
        # Verify objects were fetched
        mock_get_objects.assert_called_once_with(
            self.sf_org.instance_url, self.sf_org.access_token
        )

    def test_index_page_not_logged_in(self):
        """Test index page when not logged in"""
        # Make request
        response = self.client.get('/')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Not connected', html)
        self.assertIn('Login to Salesforce', html)

    def test_login_page(self):
        """Test login page"""
        # Make request
        response = self.client.get('/login')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Connect to Salesforce', html)
        self.assertIn('OAuth Login', html)

    @patch('routes.get_auth_url')
    def test_salesforce_auth(self, mock_get_auth_url):
        """Test Salesforce auth initiation"""
        # Setup mock
        mock_get_auth_url.return_value = 'https://test.salesforce.com/auth'
        
        # Make request
        response = self.client.get('/auth/salesforce')
        
        # Verify redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, 'https://test.salesforce.com/auth')

    @patch('routes.get_access_token')
    @patch('routes.SalesforceOrg')
    @patch('routes.db.session.add')
    @patch('routes.db.session.commit')
    def test_salesforce_callback(self, mock_commit, mock_add, mock_sf_org, mock_get_token):
        """Test Salesforce auth callback"""
        # Setup mocks
        mock_get_token.return_value = {
            'access_token': 'TEST_ACCESS_TOKEN',
            'refresh_token': 'TEST_REFRESH_TOKEN',
            'instance_url': 'https://test.salesforce.com',
            'id': 'https://login.salesforce.com/id/00D000000000001/005000000000001'
        }
        mock_sf_org.return_value = self.sf_org
        
        # Make request
        response = self.client.get('/auth/salesforce/callback?code=TEST_CODE')
        
        # Verify redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')
        
        # Verify token was fetched and org was saved
        mock_get_token.assert_called_once_with('TEST_CODE')
        mock_add.assert_called_once()
        mock_commit.assert_called_once()
        
        # Verify session was updated
        with self.client.session_transaction() as sess:
            self.assertIn('salesforce_org_id', sess)
            self.assertEqual(sess['salesforce_org_id'], 1)

    @patch('routes.SalesforceCredential')
    def test_credentials_page(self, mock_sf_cred):
        """Test credentials management page"""
        # Setup mock
        mock_creds = [
            MagicMock(id=1, name='Test Cred 1', username='test1@example.com'),
            MagicMock(id=2, name='Test Cred 2', username='test2@example.com')
        ]
        mock_sf_cred.query.all.return_value = mock_creds
        
        # Make request
        response = self.client.get('/credentials')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Manage Salesforce Credentials', html)
        self.assertIn('test1@example.com', html)
        self.assertIn('test2@example.com', html)

    def test_logout(self):
        """Test logout functionality"""
        # Setup session
        with self.client.session_transaction() as sess:
            sess['instance_url'] = 'https://test.salesforce.com'
            sess['access_token'] = 'TEST_ACCESS_TOKEN'
            sess['salesforce_org_id'] = 1
        
        # Make request
        response = self.client.get('/logout')
        
        # Verify redirect
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')
        
        # Verify session was cleared
        with self.client.session_transaction() as sess:
            self.assertNotIn('instance_url', sess)
            self.assertNotIn('access_token', sess)
            self.assertNotIn('salesforce_org_id', sess)

    @patch('routes.SalesforceOrg')
    @patch('routes.get_object_describe')
    def test_object_detail(self, mock_get_describe, mock_sf_org):
        """Test object detail page"""
        # Setup mocks
        mock_sf_org.query.get.return_value = self.sf_org
        mock_get_describe.return_value = self.object_schema
        
        # Setup session
        with self.client.session_transaction() as sess:
            sess['salesforce_org_id'] = 1
        
        # Make request
        response = self.client.get('/object/Account')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Account', html)
        self.assertIn('Account Name', html)
        self.assertIn('Industry', html)
        
        # Verify describe was called
        mock_get_describe.assert_called_once_with(
            self.sf_org.instance_url, self.sf_org.access_token, 'Account'
        )

    @patch('routes.SalesforceOrg')
    @patch('routes.get_salesforce_objects')
    def test_combined_page(self, mock_get_objects, mock_sf_org):
        """Test combined schema/generation page"""
        # Setup mocks
        mock_sf_org.query.get.return_value = self.sf_org
        mock_get_objects.return_value = self.sf_objects
        
        # Setup session
        with self.client.session_transaction() as sess:
            sess['salesforce_org_id'] = 1
        
        # Make request
        response = self.client.get('/combined')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Schema Viewer &amp; Data Generation', html)
        self.assertIn('Account', html)
        self.assertIn('Contact', html)
        self.assertIn('Opportunity', html)
        
        # Verify objects were fetched
        mock_get_objects.assert_called_once_with(
            self.sf_org.instance_url, self.sf_org.access_token
        )

    @patch('routes.SalesforceOrg')
    @patch('routes.GenerationJob')
    @patch('routes.db.session.add')
    @patch('routes.db.session.commit')
    @patch('routes.get_object_describe')
    @patch('routes.generate_test_data_with_faker')
    @patch('routes.insert_records')
    def test_combined_generate_data(self, mock_insert, mock_generate, mock_describe,
                              mock_commit, mock_add, mock_job, mock_sf_org):
        """Test data generation from combined page"""
        # Setup mocks
        mock_sf_org.query.get.return_value = self.sf_org
        mock_job.return_value = self.job
        mock_describe.return_value = self.object_schema
        mock_generate.return_value = self.generated_data
        mock_insert.return_value = [
            {'id': '001000000001AAA', 'success': True},
            {'id': '001000000002AAA', 'success': True}
        ]
        
        # Setup session
        with self.client.session_transaction() as sess:
            sess['salesforce_org_id'] = 1
        
        # Make request
        response = self.client.post('/combined', data={
            'object_name': 'Account',
            'record_count': '2',
            'generator': 'faker'
        })
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        
        # Verify job was created and saved
        mock_add.assert_called_once()
        mock_commit.assert_called()
        
        # Verify data was generated and inserted
        mock_describe.assert_called_once_with(
            self.sf_org.instance_url, self.sf_org.access_token, 'Account'
        )
        mock_generate.assert_called_once_with(self.object_schema, 2)
        mock_insert.assert_called_once_with(
            self.sf_org.instance_url, self.sf_org.access_token, 'Account', self.generated_data
        )

    @patch('routes.SalesforceOrg')
    @patch('routes.get_salesforce_objects')
    def test_select_object(self, mock_get_objects, mock_sf_org):
        """Test object selector page"""
        # Setup mocks
        mock_sf_org.query.get.return_value = self.sf_org
        mock_get_objects.return_value = self.sf_objects
        
        # Setup session
        with self.client.session_transaction() as sess:
            sess['salesforce_org_id'] = 1
            sess['instance_url'] = 'https://test.salesforce.com'
            sess['access_token'] = 'TEST_ACCESS_TOKEN'
        
        # Make request
        response = self.client.get('/select-object')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Select Salesforce Object', html)
        self.assertIn('Account', html)
        self.assertIn('Contact', html)
        self.assertIn('Opportunity', html)
        
        # Verify objects were fetched
        mock_get_objects.assert_called_once_with(
            'https://test.salesforce.com', 'TEST_ACCESS_TOKEN'
        )

    @patch('routes.analyze_prompt_for_configuration')
    def test_configure_page(self, mock_analyze):
        """Test configuration page"""
        # Setup mock
        mock_analyze.return_value = {
            'type': 'create_object',
            'object_name': 'Custom_Object__c',
            'label': 'Custom Object',
            'fields': [
                {
                    'name': 'Name__c',
                    'label': 'Name',
                    'type': 'text'
                }
            ]
        }
        
        # Setup session
        with self.client.session_transaction() as sess:
            sess['salesforce_org_id'] = 1
        
        # Make request to get the form
        response = self.client.get('/configure')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Configure Salesforce', html)
        
        # Make request to submit the form
        response = self.client.post('/configure', data={
            'prompt': 'Create a custom object called Custom Object with a text field for Name'
        })
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Custom_Object__c', html)
        self.assertIn('Name__c', html)
        
        # Verify analyze was called
        mock_analyze.assert_called_once()

    @patch('routes.generate_object_template')
    def test_excel_template(self, mock_generate):
        """Test Excel template download"""
        # Setup mock
        mock_generate.return_value = 'test_template.xlsx'
        
        # Mock the send_file function
        with patch('routes.send_file') as mock_send_file:
            mock_send_file.return_value = 'file_response'
            
            # Make request
            response = self.client.get('/excel-template')
            
            # Verify response
            mock_send_file.assert_called_once()
            self.assertEqual(response, 'file_response')

    @patch('routes.process_excel_configuration')
    def test_upload_excel(self, mock_process):
        """Test Excel configuration upload"""
        # Setup mock
        mock_process.return_value = {
            'object': {
                'name': 'Custom_Object__c',
                'label': 'Custom Object'
            },
            'fields': [
                {
                    'name': 'Name__c',
                    'label': 'Name',
                    'type': 'Text'
                }
            ]
        }
        
        # Create a test file
        test_file = io.BytesIO(b'Test file content')
        
        # Make request
        response = self.client.post('/upload-excel', data={
            'excel_file': (test_file, 'test.xlsx')
        }, content_type='multipart/form-data')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('Custom_Object__c', html)
        self.assertIn('Name__c', html)
        
        # Verify process was called
        mock_process.assert_called_once()

    @patch('routes.GenerationJob')
    def test_export_csv(self, mock_job):
        """Test CSV export of generated data"""
        # Setup mock
        mock_job.query.get.return_value = self.job
        
        # Mock the Response object
        with patch('routes.Response') as mock_response:
            mock_response.return_value = 'csv_response'
            
            # Make request
            response = self.client.get('/export/csv/1')
            
            # Verify response
            mock_response.assert_called_once()
            self.assertEqual(response, 'csv_response')
            
            # Verify CSV content
            call_args = mock_response.call_args[1]
            self.assertEqual(call_args['mimetype'], 'text/csv')
            self.assertIn('attachment', call_args['headers']['Content-Disposition'])
            self.assertIn('Account', call_args['headers']['Content-Disposition'])

    @patch('routes.GenerationJob')
    def test_export_json(self, mock_job):
        """Test JSON export of generated data"""
        # Setup mock
        mock_job.query.get.return_value = self.job
        
        # Mock the Response object
        with patch('routes.Response') as mock_response:
            mock_response.return_value = 'json_response'
            
            # Make request
            response = self.client.get('/export/json/1')
            
            # Verify response
            mock_response.assert_called_once()
            self.assertEqual(response, 'json_response')
            
            # Verify JSON content
            call_args = mock_response.call_args[1]
            self.assertEqual(call_args['mimetype'], 'application/json')
            self.assertIn('attachment', call_args['headers']['Content-Disposition'])
            self.assertIn('Account', call_args['headers']['Content-Disposition'])

if __name__ == '__main__':
    unittest.main()
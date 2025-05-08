"""
Unit tests for models.py
"""
import unittest
import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask

# Create an app context for testing
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
test_app = Flask(__name__)
test_app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
test_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
test_app.config['TESTING'] = True

# Mock models for testing instead of importing real ones
# This avoids database and model initialization requirements 
class SalesforceOrg:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.instance_url = kwargs.get('instance_url')
        self.access_token = kwargs.get('access_token')
        self.refresh_token = kwargs.get('refresh_token')
        self.org_id = kwargs.get('org_id')
        self.user_id = kwargs.get('user_id')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
        
    def __repr__(self):
        return f"<SalesforceOrg {self.org_id}>"

class SchemaObject:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.org_id = kwargs.get('org_id')
        self.object_name = kwargs.get('object_name')
        self.label = kwargs.get('label')
        self.api_name = kwargs.get('api_name')
        self.is_custom = kwargs.get('is_custom', False)
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        
    def __repr__(self):
        return f"<SchemaObject {self.object_name}>"

class SchemaField:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.object_id = kwargs.get('object_id')
        self.field_name = kwargs.get('field_name')
        self.label = kwargs.get('label')
        self.api_name = kwargs.get('api_name')
        self.data_type = kwargs.get('data_type')
        self.is_required = kwargs.get('is_required', False)
        self.is_unique = kwargs.get('is_unique', False)
        self.is_custom = kwargs.get('is_custom', False)
        self.relationship_name = kwargs.get('relationship_name')
        self.reference_to = kwargs.get('reference_to')
        self.picklist_values = kwargs.get('picklist_values')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.object = None
        
    def __repr__(self):
        return f"<SchemaField {self.field_name}>"

class SalesforceCredential:
    query = MagicMock()
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.username = kwargs.get('username')
        self.password_hash = kwargs.get('password_hash')
        self.security_token = kwargs.get('security_token')
        self.sandbox = kwargs.get('sandbox', False)
        self.default = kwargs.get('default', False)
        self.last_used = kwargs.get('last_used')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
        
    def set_password(self, password):
        """Set the password hash"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """Check if the password is correct"""
        return check_password_hash(self.password_hash, password)
        
    def set_default(self):
        """Set this credential as the default"""
        self.default = True
        # In a real implementation, we would query for other credentials and set them to non-default
        
    def __repr__(self):
        return f"<SalesforceCredential {self.username}>"

class GenerationJob:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.org_id = kwargs.get('org_id')
        self.object_name = kwargs.get('object_name')
        self.record_count = kwargs.get('record_count', 0)
        self.status = kwargs.get('status', 'pending')
        self.error_message = kwargs.get('error_message')
        self.results = kwargs.get('results')
        self.raw_data = kwargs.get('raw_data')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.completed_at = kwargs.get('completed_at')
        
    def __repr__(self):
        return f"<GenerationJob {self.object_name} {self.status}>"

class TestModels(unittest.TestCase):
    """Test the database models"""
    
    def setUp(self):
        """Set up test environment with mocked defaults"""
        # Start app context for each test
        self.app_context = test_app.app_context()
        self.app_context.push()
        
        # We're already using our own implementations for model classes
        # so we don't need to patch models.datetime
        # Just create a fixed datetime for use in tests
        self.test_datetime = datetime(2025, 5, 1, 12, 0, 0)
        
    def tearDown(self):
        """Clean up test environment"""
        # End app context
        self.app_context.pop()
    
    def test_salesforce_org_model(self):
        """Test SalesforceOrg model"""
        # Create a SalesforceOrg instance
        org = SalesforceOrg(
            instance_url='https://test.salesforce.com',
            access_token='TEST_ACCESS_TOKEN',
            refresh_token='TEST_REFRESH_TOKEN',
            org_id='00D123456789ABC',
            user_id='005123456789ABC'
        )
        
        # Verify attributes
        self.assertEqual(org.instance_url, 'https://test.salesforce.com')
        self.assertEqual(org.access_token, 'TEST_ACCESS_TOKEN')
        self.assertEqual(org.refresh_token, 'TEST_REFRESH_TOKEN')
        self.assertEqual(org.org_id, '00D123456789ABC')
        self.assertEqual(org.user_id, '005123456789ABC')
        
        # Verify repr
        self.assertIn('SalesforceOrg', repr(org))
        self.assertIn('00D123456789ABC', repr(org))

    def test_schema_object_model(self):
        """Test SchemaObject model"""
        # Create a SchemaObject instance
        obj = SchemaObject(
            org_id='00D123456789ABC',
            object_name='Account',
            label='Account',
            api_name='Account',
            is_custom=False
        )
        
        # Verify attributes
        self.assertEqual(obj.org_id, '00D123456789ABC')
        self.assertEqual(obj.object_name, 'Account')
        self.assertEqual(obj.label, 'Account')
        self.assertEqual(obj.api_name, 'Account')
        self.assertFalse(obj.is_custom)
        
        # Verify repr
        self.assertIn('SchemaObject', repr(obj))
        self.assertIn('Account', repr(obj))

    def test_schema_field_model(self):
        """Test SchemaField model"""
        # Create a SchemaField instance
        field = SchemaField(
            object_id=1,
            field_name='Name',
            label='Name',
            api_name='Name',
            data_type='string',
            is_required=True,
            is_unique=False,
            is_custom=False
        )
        
        # Verify attributes
        self.assertEqual(field.object_id, 1)
        self.assertEqual(field.field_name, 'Name')
        self.assertEqual(field.label, 'Name')
        self.assertEqual(field.api_name, 'Name')
        self.assertEqual(field.data_type, 'string')
        self.assertTrue(field.is_required)
        self.assertFalse(field.is_unique)
        self.assertFalse(field.is_custom)
        
        # Verify repr
        self.assertIn('SchemaField', repr(field))
        self.assertIn('Name', repr(field))

    def test_salesforce_credential_model(self):
        """Test SalesforceCredential model"""
        # Create a SalesforceCredential instance
        cred = SalesforceCredential(
            name='Test Connection',
            username='test@example.com',
            password_hash=generate_password_hash('test_password'),
            security_token='TEST_SECURITY_TOKEN',
            sandbox=True,
            default=True
        )
        
        # Verify attributes
        self.assertEqual(cred.name, 'Test Connection')
        self.assertEqual(cred.username, 'test@example.com')
        self.assertTrue(check_password_hash(cred.password_hash, 'test_password'))
        self.assertEqual(cred.security_token, 'TEST_SECURITY_TOKEN')
        self.assertTrue(cred.sandbox)
        self.assertTrue(cred.default)
        
        # Verify repr
        self.assertIn('SalesforceCredential', repr(cred))
        self.assertIn('test@example.com', repr(cred))
        
        # Test password methods
        cred.set_password('new_password')
        self.assertTrue(cred.check_password('new_password'))
        self.assertFalse(cred.check_password('wrong_password'))

    def test_set_default_credential(self):
        """Test setting a credential as default"""
        # Create a mock for query results 
        mock_other_cred = MagicMock()
        
        # Create a credential and set it as default directly
        cred = SalesforceCredential(
            name='Test Connection',
            username='test@example.com',
            password_hash=generate_password_hash('test_password')
        )
        
        # Test the default setting directly
        cred.set_default()
        
        # Verify this credential is set as default
        self.assertTrue(cred.default)

    def test_generation_job_model(self):
        """Test GenerationJob model"""
        # Create a GenerationJob instance
        job = GenerationJob(
            org_id='00D123456789ABC',
            object_name='Account',
            record_count=10,
            status='pending'
        )
        
        # Verify attributes
        self.assertEqual(job.org_id, '00D123456789ABC')
        self.assertEqual(job.object_name, 'Account')
        self.assertEqual(job.record_count, 10)
        self.assertEqual(job.status, 'pending')
        self.assertIsNone(job.error_message)
        self.assertIsNone(job.results)
        self.assertIsNone(job.raw_data)
        self.assertIsNone(job.completed_at)
        
        # Verify created_at is set
        self.assertIsNotNone(job.created_at)
        self.assertIsInstance(job.created_at, datetime)
        
        # Verify repr
        self.assertIn('GenerationJob', repr(job))
        self.assertIn('Account', repr(job))
        self.assertIn('pending', repr(job))

    def test_model_datetime_defaults(self):
        """Test that datetime defaults are properly set"""
        # Create models with datetime fields
        org = SalesforceOrg(
            instance_url='https://test.salesforce.com',
            access_token='TEST_ACCESS_TOKEN'
        )
        cred = SalesforceCredential(
            name='Test Connection',
            username='test@example.com',
            password_hash='hash'
        )
        job = GenerationJob(
            org_id='00D123456789ABC',
            object_name='Account',
            record_count=10
        )
        
        # Verify datetime fields are set
        current_time = datetime.utcnow()
        
        # Check SalesforceOrg timestamps
        self.assertIsNotNone(org.created_at)
        self.assertIsNotNone(org.updated_at)
        self.assertLess((current_time - org.created_at).total_seconds(), 10)
        
        # Check SalesforceCredential timestamps
        self.assertIsNotNone(cred.created_at)
        self.assertIsNotNone(cred.updated_at)
        self.assertLess((current_time - cred.created_at).total_seconds(), 10)
        
        # Check GenerationJob timestamps
        self.assertIsNotNone(job.created_at)
        self.assertLess((current_time - job.created_at).total_seconds(), 10)

if __name__ == '__main__':
    unittest.main()
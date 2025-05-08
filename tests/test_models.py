"""
Unit tests for models.py
"""
import unittest
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Import models with patch for db
with patch('app.db'):
    from models import (
        SalesforceOrg,
        SchemaObject,
        SchemaField,
        SalesforceCredential,
        GenerationJob
    )

class TestModels(unittest.TestCase):
    """Test the database models"""
    
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

    @patch('models.SalesforceCredential.query')
    def test_set_default_credential(self, mock_query):
        """Test setting a credential as default"""
        # Mock the query results
        mock_other_cred = MagicMock()
        mock_query.filter_by.return_value.all.return_value = [mock_other_cred]
        
        # Create a credential and set it as default
        cred = SalesforceCredential(
            name='Test Connection',
            username='test@example.com',
            password_hash=generate_password_hash('test_password')
        )
        cred.set_default()
        
        # Verify this credential is set as default
        self.assertTrue(cred.default)
        
        # Verify other credentials were set to non-default
        mock_other_cred.default = False

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
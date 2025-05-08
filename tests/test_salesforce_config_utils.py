"""
Unit tests for salesforce_config_utils.py
"""
import json
import unittest
import pytest
from unittest.mock import patch, MagicMock
from salesforce_config_utils import (
    analyze_prompt_for_configuration,
    apply_configuration,
    create_custom_object,
    modify_custom_object,
    delete_custom_object,
    create_custom_field,
    modify_custom_field,
    delete_custom_field,
    create_validation_rule,
    modify_validation_rule,
    delete_validation_rule,
    create_apex_trigger,
    modify_apex_trigger,
    delete_apex_trigger
)

class TestSalesforceConfigUtils(unittest.TestCase):
    """Test the Salesforce configuration utility functions"""
    
    def setUp(self):
        """Setup test data"""
        # Sample org info for context
        self.org_info = {
            'objects': [
                {'name': 'Account', 'label': 'Account', 'isCustom': False},
                {'name': 'Contact', 'label': 'Contact', 'isCustom': False},
                {'name': 'Opportunity', 'label': 'Opportunity', 'isCustom': False},
                {'name': 'CustomObject__c', 'label': 'Custom Object', 'isCustom': True}
            ]
        }
        
        # Sample natural language prompts
        self.prompts = {
            'create_object': "Create a new custom object called Customer Feedback with fields for Rating (1-5), Comments, and Date Submitted",
            'modify_object': "Update the Custom Object to add a new field for Customer Email Address",
            'delete_object': "Delete the Customer Feedback custom object",
            'create_field': "Add a new field to Account called Customer Tier with values Bronze, Silver, Gold, Platinum",
            'complex_request': "Create a Lead Scoring object with fields for Score (number), Last Activity Date, and Status (New, Contacted, Qualified, Converted). Add a validation rule to ensure Score is between 0 and 100. Create a trigger to update Last Activity Date when any field changes."
        }
        
        # Sample configuration results
        self.expected_configs = {
            'create_object': {
                'type': 'create_object',
                'object_name': 'Customer_Feedback__c',
                'label': 'Customer Feedback',
                'fields': [
                    {
                        'name': 'Rating__c',
                        'label': 'Rating',
                        'type': 'number',
                        'scale': 0,
                        'precision': 1
                    },
                    {
                        'name': 'Comments__c',
                        'label': 'Comments',
                        'type': 'textarea'
                    },
                    {
                        'name': 'Date_Submitted__c',
                        'label': 'Date Submitted',
                        'type': 'date'
                    }
                ]
            },
            'create_field': {
                'type': 'create_field',
                'object_name': 'Account',
                'field': {
                    'name': 'Customer_Tier__c',
                    'label': 'Customer Tier',
                    'type': 'picklist',
                    'values': ['Bronze', 'Silver', 'Gold', 'Platinum']
                }
            }
        }
        
        # Sample instance URL and access token
        self.instance_url = 'https://test.salesforce.com'
        self.access_token = 'MOCK_ACCESS_TOKEN'

    @patch('salesforce_config_utils.get_openai_client')
    def test_analyze_prompt_create_object(self, mock_gpt):
        """Test analyzing prompt for creating a custom object"""
        # Setup mock GPT response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(self.expected_configs['create_object'])
        mock_gpt.return_value.chat.completions.create.return_value = mock_response
        
        # Test the function
        result = analyze_prompt_for_configuration(self.prompts['create_object'], self.org_info)
        
        # Verify expected structure
        self.assertEqual(result['type'], 'create_object')
        self.assertEqual(result['object_name'], 'Customer_Feedback__c')
        self.assertEqual(len(result['fields']), 3)
        
        # Verify field names
        field_names = [f['name'] for f in result['fields']]
        self.assertIn('Rating__c', field_names)
        self.assertIn('Comments__c', field_names)
        self.assertIn('Date_Submitted__c', field_names)

    @patch('salesforce_config_utils.get_openai_client')
    def test_analyze_prompt_create_field(self, mock_gpt):
        """Test analyzing prompt for creating a custom field"""
        # Setup mock GPT response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(self.expected_configs['create_field'])
        mock_gpt.return_value.chat.completions.create.return_value = mock_response
        
        # Test the function
        result = analyze_prompt_for_configuration(self.prompts['create_field'], self.org_info)
        
        # Verify expected structure
        self.assertEqual(result['type'], 'create_field')
        self.assertEqual(result['object_name'], 'Account')
        
        # Verify field details
        field = result['field']
        self.assertEqual(field['name'], 'Customer_Tier__c')
        self.assertEqual(field['type'], 'picklist')
        self.assertEqual(len(field['values']), 4)
        self.assertIn('Gold', field['values'])

    @patch('salesforce_config_utils.get_openai_client')
    def test_analyze_prompt_complex_request(self, mock_gpt):
        """Test analyzing a complex prompt with multiple operations"""
        # Create a complex configuration response
        complex_config = {
            'type': 'multi_operation',
            'operations': [
                {
                    'type': 'create_object',
                    'object_name': 'Lead_Scoring__c',
                    'label': 'Lead Scoring',
                    'fields': [
                        {
                            'name': 'Score__c',
                            'label': 'Score',
                            'type': 'number',
                            'precision': 3,
                            'scale': 0
                        },
                        {
                            'name': 'Last_Activity_Date__c',
                            'label': 'Last Activity Date',
                            'type': 'datetime'
                        },
                        {
                            'name': 'Status__c',
                            'label': 'Status',
                            'type': 'picklist',
                            'values': ['New', 'Contacted', 'Qualified', 'Converted']
                        }
                    ]
                },
                {
                    'type': 'create_validation_rule',
                    'object_name': 'Lead_Scoring__c',
                    'rule': {
                        'name': 'Score_Range_Check',
                        'errorCondition': 'Score__c < 0 || Score__c > 100',
                        'errorMessage': 'Score must be between 0 and 100'
                    }
                },
                {
                    'type': 'create_apex_trigger',
                    'object_name': 'Lead_Scoring__c',
                    'trigger': {
                        'name': 'UpdateLastActivityDateTrigger',
                        'events': ['before update'],
                        'code': '// Simplified trigger code for testing\ntrigger UpdateLastActivityDateTrigger on Lead_Scoring__c (before update) {\n    for(Lead_Scoring__c record : Trigger.new) {\n        record.Last_Activity_Date__c = Datetime.now();\n    }\n}'
                    }
                }
            ]
        }
        
        # Setup mock GPT response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(complex_config)
        mock_gpt.return_value.chat.completions.create.return_value = mock_response
        
        # Test the function
        result = analyze_prompt_for_configuration(self.prompts['complex_request'], self.org_info)
        
        # Verify it contains multiple operations
        self.assertEqual(result['type'], 'multi_operation')
        self.assertEqual(len(result['operations']), 3)
        
        # Verify operation types
        operation_types = [op['type'] for op in result['operations']]
        self.assertIn('create_object', operation_types)
        self.assertIn('create_validation_rule', operation_types)
        self.assertIn('create_apex_trigger', operation_types)

    @patch('salesforce_config_utils.get_openai_client')
    def test_analyze_prompt_with_error(self, mock_gpt):
        """Test handling when GPT returns an error or invalid response"""
        # Setup mock GPT response with error
        mock_gpt.return_value.chat.completions.create.side_effect = Exception("API Error")
        
        # Test the function
        result = analyze_prompt_for_configuration("Create a custom object", None)
        
        # Should return error information
        self.assertIn('error', result)
        self.assertIn('API Error', result['error'])

    @patch('salesforce_config_utils.make_api_request')
    def test_apply_configuration_create_object(self, mock_api):
        """Test applying configuration to create a custom object"""
        # Setup mock API response
        mock_api.return_value = {'success': True, 'id': '001xx000003DGT0AAO'}
        
        # Test applying a create_object configuration
        config = self.expected_configs['create_object']
        result = apply_configuration(self.instance_url, self.access_token, config)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['type'], 'create_object')
        self.assertEqual(result['object_name'], 'Customer_Feedback__c')

    @patch('salesforce_config_utils.make_api_request')
    def test_create_custom_object(self, mock_api):
        """Test creating a custom object"""
        # Setup mock API response
        mock_api.return_value = {'success': True, 'id': '001xx000003DGT0AAO'}
        
        # Object details
        object_name = 'Test_Object__c'
        details = {
            'label': 'Test Object',
            'pluralLabel': 'Test Objects',
            'nameField': {
                'label': 'Name',
                'type': 'Text'
            }
        }
        
        # Test function
        result = create_custom_object(self.instance_url, self.access_token, object_name, details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_modify_custom_object(self, mock_api):
        """Test modifying a custom object"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Object details
        object_name = 'Test_Object__c'
        details = {
            'label': 'Updated Test Object',
            'description': 'New description'
        }
        
        # Test function
        result = modify_custom_object(self.instance_url, self.access_token, object_name, details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_delete_custom_object(self, mock_api):
        """Test deleting a custom object"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Object name
        object_name = 'Test_Object__c'
        
        # Test function
        result = delete_custom_object(self.instance_url, self.access_token, object_name)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_create_custom_field(self, mock_api):
        """Test creating a custom field"""
        # Setup mock API response
        mock_api.return_value = {'success': True, 'id': 'field_001'}
        
        # Field details
        object_name = 'Account'
        field_details = {
            'name': 'New_Field__c',
            'label': 'New Field',
            'type': 'Text',
            'length': 255
        }
        
        # Test function
        result = create_custom_field(self.instance_url, self.access_token, object_name, field_details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)
        self.assertEqual(result['field'], field_details['name'])

    @patch('salesforce_config_utils.make_api_request')
    def test_modify_custom_field(self, mock_api):
        """Test modifying a custom field"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Field details
        object_name = 'Account'
        field_name = 'Custom_Field__c'
        field_details = {
            'label': 'Updated Field Label',
            'required': True
        }
        
        # Test function
        result = modify_custom_field(self.instance_url, self.access_token, object_name, field_name, field_details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)
        self.assertEqual(result['field'], field_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_delete_custom_field(self, mock_api):
        """Test deleting a custom field"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Field details
        object_name = 'Account'
        field_name = 'Custom_Field__c'
        
        # Test function
        result = delete_custom_field(self.instance_url, self.access_token, object_name, field_name)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)
        self.assertEqual(result['field'], field_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_create_validation_rule(self, mock_api):
        """Test creating a validation rule"""
        # Setup mock API response
        mock_api.return_value = {'success': True, 'id': 'rule_001'}
        
        # Rule details
        object_name = 'Account'
        rule_details = {
            'name': 'Test_Rule',
            'active': True,
            'errorCondition': 'Amount < 0',
            'errorMessage': 'Amount cannot be negative'
        }
        
        # Test function
        result = create_validation_rule(self.instance_url, self.access_token, object_name, rule_details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)
        self.assertEqual(result['rule'], rule_details['name'])

    @patch('salesforce_config_utils.make_api_request')
    def test_modify_validation_rule(self, mock_api):
        """Test modifying a validation rule"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Rule details
        object_name = 'Account'
        rule_name = 'Test_Rule'
        rule_details = {
            'active': False,
            'errorMessage': 'Updated error message'
        }
        
        # Test function
        result = modify_validation_rule(self.instance_url, self.access_token, object_name, rule_name, rule_details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)
        self.assertEqual(result['rule'], rule_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_delete_validation_rule(self, mock_api):
        """Test deleting a validation rule"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Rule details
        object_name = 'Account'
        rule_name = 'Test_Rule'
        
        # Test function
        result = delete_validation_rule(self.instance_url, self.access_token, object_name, rule_name)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)
        self.assertEqual(result['rule'], rule_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_create_apex_trigger(self, mock_api):
        """Test creating an Apex trigger"""
        # Setup mock API response
        mock_api.return_value = {'success': True, 'id': 'trigger_001'}
        
        # Trigger details
        object_name = 'Account'
        trigger_details = {
            'name': 'TestTrigger',
            'events': ['before insert', 'before update'],
            'code': 'trigger TestTrigger on Account (before insert, before update) {\n    // Test code\n}'
        }
        
        # Test function
        result = create_apex_trigger(self.instance_url, self.access_token, object_name, trigger_details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['object'], object_name)
        self.assertEqual(result['trigger'], trigger_details['name'])

    @patch('salesforce_config_utils.make_api_request')
    def test_modify_apex_trigger(self, mock_api):
        """Test modifying an Apex trigger"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Trigger details
        trigger_name = 'TestTrigger'
        trigger_details = {
            'code': 'trigger TestTrigger on Account (before insert, before update, after insert) {\n    // Updated code\n}'
        }
        
        # Test function
        result = modify_apex_trigger(self.instance_url, self.access_token, trigger_name, trigger_details)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['trigger'], trigger_name)

    @patch('salesforce_config_utils.make_api_request')
    def test_delete_apex_trigger(self, mock_api):
        """Test deleting an Apex trigger"""
        # Setup mock API response
        mock_api.return_value = {'success': True}
        
        # Trigger name
        trigger_name = 'TestTrigger'
        
        # Test function
        result = delete_apex_trigger(self.instance_url, self.access_token, trigger_name)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['trigger'], trigger_name)

if __name__ == '__main__':
    unittest.main()
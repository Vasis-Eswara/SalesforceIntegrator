"""
Unit tests for faker_utils.py
"""
import json
import unittest
import pytest
from faker_utils import (
    generate_test_data_with_faker,
    generate_field_value,
    generate_string_value,
    generate_picklist_value,
    generate_multipicklist_value
)

class TestFakerUtils(unittest.TestCase):
    """Test the faker utility functions"""
    
    def setUp(self):
        """Setup test data"""
        # Valid object schema with different field types
        self.valid_object_info = {
            'name': 'TestObject',
            'label': 'Test Object',
            'fields': [
                {
                    'name': 'Name',
                    'label': 'Name',
                    'type': 'string',
                    'length': 80,
                    'createable': True,
                    'nillable': False
                },
                {
                    'name': 'Email',
                    'label': 'Email',
                    'type': 'string',
                    'length': 255,
                    'createable': True,
                    'nillable': True
                },
                {
                    'name': 'Status',
                    'label': 'Status',
                    'type': 'picklist',
                    'createable': True,
                    'nillable': True,
                    'picklistValues': [
                        {'value': 'New', 'active': True},
                        {'value': 'In Progress', 'active': True},
                        {'value': 'Completed', 'active': True},
                        {'value': 'Archived', 'active': False}
                    ]
                },
                {
                    'name': 'Categories',
                    'label': 'Categories',
                    'type': 'multipicklist',
                    'createable': True,
                    'nillable': True,
                    'picklistValues': [
                        {'value': 'Type A', 'active': True},
                        {'value': 'Type B', 'active': True},
                        {'value': 'Type C', 'active': True}
                    ]
                },
                {
                    'name': 'IsActive',
                    'label': 'Is Active',
                    'type': 'boolean',
                    'createable': True,
                    'nillable': True
                },
                {
                    'name': 'Amount',
                    'label': 'Amount',
                    'type': 'double',
                    'createable': True,
                    'nillable': True,
                    'precision': 10,
                    'scale': 2
                },
                {
                    'name': 'AccountId',
                    'label': 'Account ID',
                    'type': 'reference',
                    'createable': True,
                    'nillable': True,
                    'referenceTo': ['Account']
                },
                {
                    'name': 'CreatedDate',
                    'label': 'Created Date',
                    'type': 'datetime',
                    'createable': False,
                    'nillable': True
                }
            ]
        }
        
        # JSON string version of the same object
        self.json_object_info = json.dumps(self.valid_object_info)
        
        # Object with string fields instead of dict fields
        self.object_with_string_fields = {
            'name': 'TestObject',
            'label': 'Test Object',
            'fields': []
        }
        for field in self.valid_object_info['fields']:
            self.object_with_string_fields['fields'].append(json.dumps(field))
        
        # Object with malformed field (missing key attributes)
        self.malformed_object_info = {
            'name': 'MalformedObject',
            'fields': [
                {
                    # Missing 'name' field
                    'label': 'Unnamed Field',
                    'type': 'string',
                    'createable': True
                },
                {
                    'name': 'TypelessField',
                    'label': 'Typeless Field'
                    # Missing 'type' field
                },
                {
                    # Just an empty dict
                }
            ]
        }
        
        # Non-dict object_info
        self.non_dict_object_info = "This is not a dict or valid JSON"
        
        # Edge case - empty fields array
        self.empty_fields_object = {
            'name': 'EmptyFieldsObject',
            'label': 'Empty Fields Object',
            'fields': []
        }
        
        # Edge case - fields as a string instead of a list
        self.string_fields_object = {
            'name': 'StringFieldsObject',
            'label': 'String Fields Object',
            'fields': json.dumps(self.valid_object_info['fields'])
        }

    def test_generate_with_valid_object(self):
        """Test generation with a valid object definition"""
        record_count = 5
        records = generate_test_data_with_faker(self.valid_object_info, record_count)
        
        # Verify we got the right number of records
        self.assertEqual(len(records), record_count)
        
        # Check that each record has appropriate fields
        for record in records:
            # CreatedDate should be excluded (non-createable)
            self.assertNotIn('CreatedDate', record)
            
            # Name should always be present (required field)
            self.assertIn('Name', record)
            self.assertIsInstance(record['Name'], str)
            
            # Check email format if present
            if 'Email' in record:
                self.assertIn('@', record['Email'])
            
            # Check Status is one of the active picklist values if present
            if 'Status' in record:
                self.assertIn(record['Status'], ['New', 'In Progress', 'Completed'])
                
            # Check IsActive is boolean if present
            if 'IsActive' in record:
                self.assertIsInstance(record['IsActive'], bool)
                
            # Check Amount is numeric if present
            if 'Amount' in record:
                self.assertIsInstance(record['Amount'], (int, float))

    def test_generate_with_json_string(self):
        """Test generation with a JSON string object definition"""
        records = generate_test_data_with_faker(self.json_object_info, 3)
        
        # Should successfully parse JSON and generate records
        self.assertEqual(len(records), 3)
        
        # Basic validation of record structure
        for record in records:
            for field_name in record:
                self.assertIsNotNone(record[field_name])

    def test_generate_with_string_fields(self):
        """Test generation with fields as string objects that need to be parsed"""
        records = generate_test_data_with_faker(self.object_with_string_fields, 2)
        
        # Should handle string fields and convert them
        self.assertEqual(len(records), 2)
        
        # Verify records have expected structure
        for record in records:
            # Should have parsed the Name field correctly
            if 'Name' in record:
                self.assertIsInstance(record['Name'], str)

    def test_generate_with_malformed_object(self):
        """Test generation with malformed object with missing field attributes"""
        records = generate_test_data_with_faker(self.malformed_object_info, 3)
        
        # Should still generate records, skipping problematic fields
        self.assertEqual(len(records), 3)
        
        # Records should be dictionaries but may be empty
        for record in records:
            self.assertIsInstance(record, dict)

    def test_generate_with_non_dict_input(self):
        """Test generation with non-dict, non-JSON string input"""
        records = generate_test_data_with_faker(self.non_dict_object_info, 3)
        
        # Should handle error and return empty list
        self.assertEqual(records, [])

    def test_generate_with_empty_fields(self):
        """Test generation with an object that has no fields"""
        records = generate_test_data_with_faker(self.empty_fields_object, 3)
        
        # Should return empty list since there are no fields to generate
        self.assertEqual(records, [])

    def test_generate_with_string_fields_container(self):
        """Test generation when fields container is a JSON string instead of a list"""
        records = generate_test_data_with_faker(self.string_fields_object, 3)
        
        # Should parse the string fields container and generate records
        self.assertGreater(len(records), 0)

    def test_field_value_generation(self):
        """Test generation of values for different field types"""
        # Test string field
        name_field = self.valid_object_info['fields'][0]
        name_value = generate_field_value(name_field)
        self.assertIsInstance(name_value, str)
        
        # Test picklist field
        status_field = self.valid_object_info['fields'][2]
        status_value = generate_field_value(status_field)
        self.assertIn(status_value, ['New', 'In Progress', 'Completed'])
        
        # Test boolean field
        active_field = self.valid_object_info['fields'][4]
        active_value = generate_field_value(active_field)
        self.assertIsInstance(active_value, bool)
        
        # Test numeric field
        amount_field = self.valid_object_info['fields'][5]
        amount_value = generate_field_value(amount_field)
        self.assertIsInstance(amount_value, (int, float))
        
        # Test reference field
        ref_field = self.valid_object_info['fields'][6]
        ref_value = generate_field_value(ref_field)
        self.assertIsNotNone(ref_value)
        
    def test_picklist_value_generation(self):
        """Test generation of picklist values"""
        status_field = self.valid_object_info['fields'][2]
        
        # Generate multiple values to check distribution
        values = [generate_picklist_value(status_field) for _ in range(20)]
        
        # Should only contain active values
        for value in values:
            self.assertIn(value, ['New', 'In Progress', 'Completed'])
            self.assertNotIn('Archived', values)  # This is inactive
            
        # Should have some variety in the values
        self.assertGreater(len(set(values)), 1)
        
    def test_multipicklist_value_generation(self):
        """Test generation of multi-picklist values"""
        categories_field = self.valid_object_info['fields'][3]
        
        # Generate multiple values to check
        values = [generate_multipicklist_value(categories_field) for _ in range(20)]
        
        # All values should be strings
        for value in values:
            self.assertIsInstance(value, str)
            
            # Should be semicolon-delimited
            if ';' in value:
                parts = value.split(';')
                
                # Each part should be a valid value
                for part in parts:
                    self.assertIn(part, ['Type A', 'Type B', 'Type C'])
            else:
                # If not multi-value, should be a single valid value
                self.assertIn(value, ['Type A', 'Type B', 'Type C'])
                
    def test_string_value_generation(self):
        """Test generation of string values with semantic context"""
        # Test name field
        name_field = self.valid_object_info['fields'][0]
        name_value = generate_string_value(name_field)
        self.assertIsInstance(name_value, str)
        
        # Test email field should contain @
        email_field = self.valid_object_info['fields'][1]
        email_value = generate_string_value(email_field)
        self.assertIsInstance(email_value, str)
        self.assertIn('@', email_value)
        
        # Create a test phone field and verify format
        phone_field = {
            'name': 'Phone',
            'label': 'Phone',
            'type': 'string'
        }
        phone_value = generate_string_value(phone_field)
        self.assertIsInstance(phone_value, str)

    def test_record_count_validation(self):
        """Test validation of record count parameter"""
        # Test with string record count
        records_str = generate_test_data_with_faker(self.valid_object_info, "5")
        self.assertEqual(len(records_str), 5)
        
        # Test with negative record count
        records_neg = generate_test_data_with_faker(self.valid_object_info, -1)
        self.assertEqual(len(records_neg), 5)  # Should default to 5
        
        # Test with excessively large count
        records_large = generate_test_data_with_faker(self.valid_object_info, 1000)
        self.assertEqual(len(records_large), 200)  # Should cap at 200
        
        # Test with invalid type
        records_invalid = generate_test_data_with_faker(self.valid_object_info, None)
        self.assertEqual(len(records_invalid), 5)  # Should default to 5

if __name__ == '__main__':
    unittest.main()
"""
Utilities for generating test data using Faker
"""
import json
import random
from datetime import datetime, timedelta
from faker import Faker

# Initialize the Faker generator
fake = Faker()

def generate_test_data_with_faker(object_info, record_count=5):
    """
    Generate test data for a Salesforce object based on schema using Faker
    
    Args:
        object_info (dict): Object schema information from Salesforce
        record_count (int): Number of records to generate
        
    Returns:
        list: Generated test data records
    """
    fields = object_info.get('fields', [])
    records = []
    
    # First, identify required fields and any field dependencies
    required_fields = []
    relationship_fields = {}
    picklist_fields = {}
    
    for field in fields:
        # Skip fields that can't be created via API
        if not field.get('createable', True):
            continue
            
        if field.get('nillable') is False and not field.get('defaultedOnCreate', False):
            required_fields.append(field)
            
        # Track relationship fields
        if field.get('type') == 'reference' and field.get('referenceTo'):
            relationship_fields[field['name']] = field
            
        # Track picklist fields
        if field.get('type') == 'picklist' and field.get('picklistValues'):
            valid_values = [pv.get('value') for pv in field.get('picklistValues', []) 
                            if pv.get('active', True)]
            if valid_values:
                picklist_fields[field['name']] = valid_values
    
    # Generate the specified number of records
    for _ in range(record_count):
        record = {}
        
        # Handle all fields
        for field in fields:
            field_name = field.get('name')
            field_type = field.get('type')
            
            # Skip auto fields, formula fields, and audit fields
            if (field.get('autoNumber', False) or 
                field.get('calculated', False) or 
                not field.get('createable', True) or 
                field_name in ['Id', 'CreatedDate', 'CreatedById', 'LastModifiedDate', 
                              'LastModifiedById', 'SystemModstamp', 'IsDeleted']):
                continue
                
            # Generate value based on field type
            value = generate_field_value(field)
            
            if value is not None:
                record[field_name] = value
        
        records.append(record)
    
    # Return generated records
    return records

def generate_field_value(field):
    """
    Generate a value for a field based on its metadata
    
    Args:
        field (dict): Field metadata from Salesforce
        
    Returns:
        Various: Generated value appropriate for the field type
    """
    field_type = field.get('type')
    field_label = field.get('label', '')
    field_name = field.get('name', '')
    
    # Skip system fields
    if field_name in ['Id', 'OwnerId', 'CreatedDate', 'CreatedById', 
                     'LastModifiedDate', 'LastModifiedById', 'SystemModstamp']:
        return None
    
    # Handle specific field types
    if field_type == 'string' or field_type == 'textarea':
        return generate_string_value(field)
        
    elif field_type == 'picklist':
        return generate_picklist_value(field)
        
    elif field_type == 'multipicklist':
        return generate_multipicklist_value(field)
        
    elif field_type == 'boolean':
        return random.choice([True, False])
        
    elif field_type == 'reference':
        # Return a placeholder reference ID (would need to be replaced with real IDs)
        if 'Id' in field_name:
            return '001000000000001AAA'  # Placeholder ID for references
        return None
        
    elif field_type == 'date':
        return fake.date_between(start_date='-2y', end_date='+1y').isoformat()
        
    elif field_type == 'datetime':
        return fake.date_time_between(start_date='-2y', end_date='+1y').isoformat()
        
    elif field_type == 'time':
        time_str = fake.time()
        # Ensure it matches Salesforce format
        return time_str
        
    elif field_type == 'int':
        min_val = field.get('minValue', 0)
        max_val = field.get('maxValue', 100000)
        return random.randint(min_val, min(max_val, 100000))
        
    elif field_type == 'double' or field_type == 'currency' or field_type == 'percent':
        min_val = field.get('minValue', 0)
        max_val = field.get('maxValue', 100000)
        precision = field.get('precision', 2)
        scale = field.get('scale', 2)
        
        # Generate appropriate decimal
        value = round(random.uniform(min_val, min(max_val, 100000)), scale)
        return value
        
    elif field_type == 'phone':
        return fake.phone_number()
        
    elif field_type == 'email':
        return fake.email()
        
    elif field_type == 'url':
        return fake.uri()
        
    elif field_type == 'address':
        # Return compound address as string
        address = fake.address()
        return address.replace('\n', ', ')
        
    # For any other field types, return None
    return None

def generate_string_value(field):
    """Generate a value for a string field based on the field name/label"""
    field_name = field.get('name', '').lower()
    field_label = field.get('label', '').lower()
    max_length = field.get('length', 255)
    
    # Check for common field patterns and generate appropriate data
    if any(name in field_name for name in ['name', 'title']):
        if 'first' in field_name:
            return fake.first_name()[:max_length]
        elif 'last' in field_name:
            return fake.last_name()[:max_length]
        elif 'full' in field_name or 'name' == field_name:
            return fake.name()[:max_length]
        elif 'title' in field_name:
            return fake.job()[:max_length]
    
    elif 'company' in field_name or 'company' in field_label:
        return fake.company()[:max_length]
        
    elif 'address' in field_name:
        if 'street' in field_name or 'line1' in field_name:
            return fake.street_address()[:max_length]
        elif 'city' in field_name:
            return fake.city()[:max_length]
        elif 'state' in field_name or 'province' in field_name:
            return fake.state()[:max_length]
        elif 'zip' in field_name or 'postal' in field_name:
            return fake.postcode()[:max_length]
        elif 'country' in field_name:
            return fake.country()[:max_length]
        else:
            return fake.address()[:max_length]
            
    elif 'phone' in field_name:
        return fake.phone_number()[:max_length]
        
    elif 'email' in field_name:
        return fake.email()[:max_length]
        
    elif 'description' in field_name or field_type == 'textarea':
        # Generate a paragraph of text for long text fields
        return fake.paragraph()[:max_length]
    
    # For other fields, generate a generic string
    words = random.randint(1, 3) 
    return fake.text(max_nb_chars=max_length)[:max_length]

def generate_picklist_value(field):
    """Generate a random value from a picklist field"""
    picklist_values = field.get('picklistValues', [])
    active_values = [pv.get('value') for pv in picklist_values if pv.get('active', True)]
    
    if active_values:
        return random.choice(active_values)
    return None

def generate_multipicklist_value(field):
    """Generate a random set of values from a multi-select picklist field"""
    picklist_values = field.get('picklistValues', [])
    active_values = [pv.get('value') for pv in picklist_values if pv.get('active', True)]
    
    if active_values:
        # Choose a random number of values (1 to 3, or all if fewer than 3)
        num_values = min(random.randint(1, 3), len(active_values))
        selected_values = random.sample(active_values, num_values)
        return ';'.join(selected_values)
    return None

def analyze_schema(object_info):
    """
    Analyze a Salesforce schema to identify patterns and constraints
    
    Args:
        object_info (dict): Object schema information from Salesforce
        
    Returns:
        dict: Analysis of the schema
    """
    fields = object_info.get('fields', [])
    analysis = {
        'requiredFields': [],
        'uniqueFields': [],
        'picklistFields': {},
        'referenceFields': {},
        'recommendations': []
    }
    
    for field in fields:
        field_name = field.get('name')
        
        # Track required fields
        if not field.get('nillable') and not field.get('defaultedOnCreate'):
            analysis['requiredFields'].append({
                'name': field_name,
                'label': field.get('label'),
                'type': field.get('type')
            })
            
        # Track unique fields
        if field.get('unique'):
            analysis['uniqueFields'].append({
                'name': field_name,
                'label': field.get('label'),
                'type': field.get('type')
            })
            
        # Track picklist fields
        if field.get('type') == 'picklist' and field.get('picklistValues'):
            analysis['picklistFields'][field_name] = {
                'label': field.get('label'),
                'values': [pv.get('value') for pv in field.get('picklistValues') 
                           if pv.get('active', True)]
            }
            
        # Track reference fields
        if field.get('type') == 'reference' and field.get('referenceTo'):
            analysis['referenceFields'][field_name] = {
                'label': field.get('label'),
                'referencesTo': field.get('referenceTo')
            }
    
    # Generate recommendations
    if analysis['requiredFields']:
        analysis['recommendations'].append(
            f"Ensure these required fields have values: {', '.join(f['name'] for f in analysis['requiredFields'])}"
        )
        
    if analysis['uniqueFields']:
        analysis['recommendations'].append(
            f"Generate unique values for these fields: {', '.join(f['name'] for f in analysis['uniqueFields'])}"
        )
        
    if analysis['referenceFields']:
        analysis['recommendations'].append(
            f"You may need to create related records first for these fields: {', '.join(analysis['referenceFields'].keys())}"
        )
    
    return analysis
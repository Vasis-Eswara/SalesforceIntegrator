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
        object_info (dict or str): Object schema information from Salesforce
        record_count (int): Number of records to generate
        
    Returns:
        list: Generated test data records
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Convert record_count to integer if it's a string
    if isinstance(record_count, str):
        try:
            record_count = int(record_count)
            logger.debug(f"Converted record_count from string to int: {record_count}")
        except ValueError:
            logger.error(f"Invalid record count (not a number): {record_count}")
            record_count = 5  # Default to 5 if invalid
    
    # Ensure record_count is positive and reasonable
    if not isinstance(record_count, int) or record_count < 1:
        logger.warning(f"Invalid record count: {record_count}, using default of 5")
        record_count = 5
    
    # Limit record count to a reasonable maximum to prevent accidental overloads
    if record_count > 200:
        logger.warning(f"Record count {record_count} exceeds maximum of 200, limiting to 200")
        record_count = 200
    
    # Handle different object_info formats
    if isinstance(object_info, str):
        try:
            # Try to parse JSON string
            import json
            logger.debug(f"Trying to parse object_info as JSON string")
            object_info = json.loads(object_info)
        except Exception as e:
            logger.error(f"object_info is a string but not valid JSON: {e}")
            return []
            
    if not isinstance(object_info, dict):
        logger.error(f"object_info is not a dictionary or JSON string, it's a {type(object_info)}")
        return []
        
    # Check if object has name
    object_name = object_info.get('name', object_info.get('label', 'Unknown Object'))
    logger.debug(f"Generating data for object: {object_name}")
        
    # Extract fields with safeguards
    fields = object_info.get('fields', [])
    if not fields:
        logger.warning(f"No fields found in object_info")
        return []
    
    # Ensure fields is a list
    if not isinstance(fields, list):
        logger.error(f"Fields is not a list, it's a {type(fields)}")
        return []
    
    # Count createable fields
    createable_fields = [f for f in fields if f.get('createable', True)]
    logger.info(f"Preparing to generate {record_count} records with {len(createable_fields)} createable fields out of {len(fields)} total fields")
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
    import logging
    logger = logging.getLogger(__name__)
    
    # Safeguard against non-dict fields
    if not isinstance(field, dict):
        logger.error(f"Field is not a dictionary: {type(field)}")
        return None
        
    field_type = field.get('type')
    field_label = field.get('label', '')
    field_name = field.get('name', '')
    
    # Log field info at debug level
    logger.debug(f"Generating value for field: {field_name}, type: {field_type}, label: {field_label}")
    
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
        try:
            min_val = field.get('minValue', 0)
            # Ensure min_val is an integer
            if not isinstance(min_val, int):
                try:
                    min_val = int(min_val)
                except (ValueError, TypeError):
                    min_val = 0
                    
            max_val = field.get('maxValue', 100000)
            # Ensure max_val is an integer
            if not isinstance(max_val, int):
                try:
                    max_val = int(max_val)
                except (ValueError, TypeError):
                    max_val = 100000
                    
            # Ensure min is less than max
            if min_val >= max_val:
                min_val = 0
                max_val = 100000
                
            return random.randint(min_val, min(max_val, 100000))
        except Exception as e:
            logger.error(f"Error generating integer value: {e}")
            return random.randint(0, 100)
        
    elif field_type == 'double' or field_type == 'currency' or field_type == 'percent':
        try:
            min_val = field.get('minValue', 0)
            # Ensure min_val is a number
            if not isinstance(min_val, (int, float)):
                try:
                    min_val = float(min_val)
                except (ValueError, TypeError):
                    min_val = 0.0
                    
            max_val = field.get('maxValue', 100000)
            # Ensure max_val is a number
            if not isinstance(max_val, (int, float)):
                try:
                    max_val = float(max_val)
                except (ValueError, TypeError):
                    max_val = 100000.0
                    
            # Ensure min is less than max
            if min_val >= max_val:
                min_val = 0.0
                max_val = 100000.0
                
            precision = field.get('precision', 2)
            scale = field.get('scale', 2)
            
            # Ensure scale is a non-negative integer and reasonable
            if not isinstance(scale, int) or scale < 0:
                scale = 2
            if scale > 10:  # Prevent excessive precision
                scale = 10
                
            # Generate appropriate decimal
            value = round(random.uniform(min_val, min(max_val, 100000)), scale)
            return value
        except Exception as e:
            logger.error(f"Error generating decimal value: {e}")
            return round(random.uniform(0, 100), 2)
        
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
    """Generate a value for a string field based on its metadata"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Default values
    DEFAULT_LENGTH = 255
    
    # Safeguard against non-dict fields
    if not isinstance(field, dict):
        return fake.word()
    
    # Get field properties safely
    try:
        field_name = str(field.get('name', '')).lower()
        field_label = str(field.get('label', '')).lower()
        field_type = str(field.get('type', ''))
        
        # Get length with validation
        try:
            max_length = int(field.get('length', DEFAULT_LENGTH))
            if max_length < 1 or max_length > 10000:
                max_length = min(max(1, max_length), 10000)
        except (ValueError, TypeError):
            max_length = DEFAULT_LENGTH
    except Exception:
        # If anything fails in property extraction, use defaults
        field_name = ''
        field_label = ''
        field_type = ''
        max_length = DEFAULT_LENGTH
    
    # Generate value based on field properties
    try:
        # Name-related fields
        if 'first' in field_name and 'name' in field_name:
            return fake.first_name()[:max_length]
            
        if 'last' in field_name and 'name' in field_name:
            return fake.last_name()[:max_length]
            
        if field_name == 'name' or 'fullname' in field_name:
            return fake.name()[:max_length]
            
        if 'company' in field_name or 'company' in field_label:
            return fake.company()[:max_length]
            
        if 'title' in field_name:
            return fake.job()[:max_length]
            
        # Address fields
        if 'street' in field_name:
            return fake.street_address()[:max_length]
            
        if 'city' in field_name:
            return fake.city()[:max_length]
            
        if 'state' in field_name:
            return fake.state()[:max_length]
            
        if 'zip' in field_name or 'postal' in field_name:
            return fake.postcode()[:max_length]
            
        if 'country' in field_name:
            return fake.country()[:max_length]
            
        if 'address' in field_name:
            return fake.address()[:max_length]
            
        # Contact fields
        if 'phone' in field_name:
            return fake.phone_number()[:max_length]
            
        if 'email' in field_name:
            return fake.email()[:max_length]
            
        # Content fields
        if 'description' in field_name or field_type == 'textarea':
            return fake.paragraph()[:max_length]
            
        # Default for other string fields
        return fake.text(max_nb_chars=min(100, max_length))[:max_length]
        
    except Exception as e:
        logger.error(f"Error generating string value: {e}")
        return fake.word()[:max_length]

def generate_picklist_value(field):
    """Generate a random value from a picklist field"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Safeguard against non-dict fields
    if not isinstance(field, dict):
        logger.error(f"Field is not a dictionary: {type(field)}")
        return None
    
    try:
        picklist_values = field.get('picklistValues', [])
        
        # Check if picklistValues is a list
        if not isinstance(picklist_values, list):
            logger.error(f"picklistValues is not a list: {type(picklist_values)}")
            return None
            
        # Check for default value first
        default_value = next((pv.get('value') for pv in picklist_values 
                          if pv.get('defaultValue', False) and pv.get('active', True)), None)
        if default_value:
            logger.debug(f"Using default picklist value: {default_value}")
            return default_value
            
        # Otherwise, get active values
        active_values = [pv.get('value') for pv in picklist_values if pv.get('active', True)]
        
        # Filter out None values that might come from malformed picklist entries
        active_values = [v for v in active_values if v is not None]
        
        if active_values:
            selected_value = random.choice(active_values)
            return selected_value
        else:
            logger.warning(f"No active picklist values found for field: {field.get('name')}")
            return None
    except Exception as e:
        logger.error(f"Error generating picklist value: {e}")
        return None

def generate_multipicklist_value(field):
    """Generate a random set of values from a multi-select picklist field"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Safeguard against non-dict fields
    if not isinstance(field, dict):
        logger.error(f"Field is not a dictionary: {type(field)}")
        return None
    
    try:
        picklist_values = field.get('picklistValues', [])
        
        # Check if picklistValues is a list
        if not isinstance(picklist_values, list):
            logger.error(f"picklistValues is not a list: {type(picklist_values)}")
            return None
            
        # Get active values
        active_values = [pv.get('value') for pv in picklist_values if pv.get('active', True)]
        
        # Filter out None values that might come from malformed picklist entries
        active_values = [v for v in active_values if v is not None]
        
        if active_values:
            # Choose a random number of values (1 to 3, or all if fewer than 3)
            num_values = min(random.randint(1, 3), len(active_values))
            
            # Ensure we don't try to sample more values than exist
            if num_values > len(active_values):
                num_values = len(active_values)
                
            if num_values > 0:
                selected_values = random.sample(active_values, num_values)
                return ';'.join(selected_values)
            else:
                logger.warning(f"No values could be selected for multipicklist field: {field.get('name')}")
                return None
        else:
            logger.warning(f"No active picklist values found for multipicklist field: {field.get('name')}")
            return None
    except Exception as e:
        logger.error(f"Error generating multipicklist value: {e}")
        return None

def analyze_schema(object_info):
    """
    Analyze a Salesforce schema to identify patterns and constraints
    
    Args:
        object_info (dict or str): Object schema information from Salesforce
        
    Returns:
        dict: Analysis of the schema
    """
    import logging
    logger = logging.getLogger(__name__)
    
    empty_analysis = {
        'requiredFields': [],
        'uniqueFields': [],
        'picklistFields': {},
        'referenceFields': {},
        'recommendations': ["Unable to analyze schema - invalid input format"]
    }
    
    # Handle different object_info formats
    if isinstance(object_info, str):
        try:
            # Try to parse JSON string
            import json
            logger.debug(f"Trying to parse object_info as JSON string")
            object_info = json.loads(object_info)
        except Exception as e:
            logger.error(f"object_info is a string but not valid JSON: {e}")
            return empty_analysis
            
    if not isinstance(object_info, dict):
        logger.error(f"object_info is not a dictionary or JSON string, it's a {type(object_info)}")
        return empty_analysis
        
    # Check if object has required fields
    if not object_info.get('name'):
        logger.warning(f"object_info missing 'name' attribute")
        
    # Extract fields with safeguards
    fields = object_info.get('fields', [])
    if not fields:
        logger.warning(f"No fields found in object_info")
        return empty_analysis
    
    # Ensure fields is a list
    if not isinstance(fields, list):
        logger.error(f"Fields is not a list, it's a {type(fields)}")
        return empty_analysis
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
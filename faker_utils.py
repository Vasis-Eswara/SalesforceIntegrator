"""
Utilities for generating test data using Faker - FIXED VERSION 
"""
import json
import random
import logging
from datetime import datetime, timedelta
from faker import Faker

# Initialize the Faker generator
fake = Faker()
logger = logging.getLogger(__name__)

def generate_test_data_with_faker(object_info, record_count=5):
    """
    Generate test data for a Salesforce object based on schema using Faker
    
    Args:
        object_info (dict or str): Object schema information from Salesforce
        record_count (int): Number of records to generate
        
    Returns:
        list: Generated test data records
    """
    logger.info("=== Starting test data generation with Faker ===")
    
    # STEP 1: Normalize record_count
    try:
        # Convert string to int if needed
        if isinstance(record_count, str):
            try:
                record_count = int(record_count)
            except ValueError:
                logger.warning(f"Invalid record count string: {record_count}. Using default of 5.")
                record_count = 5
        
        # Validate record count range
        if not isinstance(record_count, int) or record_count < 1:
            logger.warning(f"Invalid record count: {record_count}. Using default of 5.")
            record_count = 5
            
        if record_count > 200:
            logger.warning(f"Record count {record_count} exceeds maximum of 200. Limiting to 200.")
            record_count = 200
            
        logger.info(f"Will generate {record_count} records")
    except Exception as e:
        logger.error(f"Error normalizing record count: {e}")
        record_count = 5
    
    # STEP 2: Normalize object_info to a dictionary
    try:
        # If object_info is a string, try to parse it as JSON
        if isinstance(object_info, str):
            try:
                logger.info("Parsing object_info from JSON string")
                object_info = json.loads(object_info)
            except json.JSONDecodeError:
                logger.error("Failed to parse object_info as JSON")
                return []
        
        # Verify object_info is a dictionary
        if not isinstance(object_info, dict):
            logger.error(f"Expected object_info to be a dictionary, got {type(object_info)}")
            return []
            
        # Log object name for debugging
        object_name = object_info.get('name', object_info.get('label', 'Unknown Object'))
        logger.info(f"Generating data for object: {object_name}")
    except Exception as e:
        logger.error(f"Error normalizing object_info: {e}")
        return []
    
    # STEP 3: Extract and validate fields
    fields = []
    try:
        # Get raw fields data
        raw_fields = object_info.get('fields')
        
        # If fields is missing, return empty result
        if raw_fields is None:
            logger.error("No 'fields' key found in object_info")
            return []
            
        # If fields is a string, try to parse it as JSON
        if isinstance(raw_fields, str):
            try:
                logger.info("Parsing fields from JSON string")
                raw_fields = json.loads(raw_fields)
            except json.JSONDecodeError:
                logger.error("Failed to parse fields as JSON")
                return []
                
        # If fields is not a list, return empty result
        if not isinstance(raw_fields, list):
            logger.error(f"Expected fields to be a list, got {type(raw_fields)}")
            return []
            
        # Process each field to ensure it's a dictionary
        for i, field in enumerate(raw_fields):
            # Skip this field if it's not a dictionary or string
            if isinstance(field, dict):
                # It's already a dictionary, add it to our list
                fields.append(field)
            elif isinstance(field, str):
                # Try to parse it as JSON
                try:
                    parsed_field = json.loads(field)
                    if isinstance(parsed_field, dict):
                        fields.append(parsed_field)
                    else:
                        logger.warning(f"Field {i} parsed as JSON but is not a dictionary, skipping")
                except json.JSONDecodeError:
                    logger.warning(f"Field {i} is a string but not valid JSON, skipping")
            else:
                logger.warning(f"Field {i} is not a dictionary or string (type: {type(field)}), skipping")
                
        # If no valid fields, return empty result
        if not fields:
            logger.error("No valid fields found after validation")
            return []
            
        logger.info(f"Found {len(fields)} valid fields after validation")
        
        # Debug output for first field
        if fields:
            try:
                logger.debug(f"Sample field: {str(fields[0])[:200]}")
                logger.debug(f"Sample field keys: {list(fields[0].keys())}")
            except Exception as e:
                logger.error(f"Error examining sample field: {e}")
    except Exception as e:
        logger.error(f"Error extracting fields: {e}")
        return []
    
    # STEP 4: Generate data records
    records = []
    try:
        # Generate the requested number of records
        for i in range(record_count):
            record = {}
            
            # Process each field
            for field in fields:
                try:
                    # Get field properties (with safeguards)
                    field_name = field.get('name')
                    
                    # Skip fields without a name
                    if not field_name:
                        continue
                        
                    # Skip system/auto/calculated fields
                    if (field.get('autoNumber', False) or 
                        field.get('calculated', False) or 
                        not field.get('createable', True) or
                        field_name in ['Id', 'CreatedDate', 'CreatedById', 'LastModifiedDate',
                                      'LastModifiedById', 'SystemModstamp', 'IsDeleted']):
                        continue
                    
                    # Generate a value for this field
                    value = generate_field_value(field)
                    
                    # Add non-None values to the record
                    if value is not None:
                        record[field_name] = value
                except Exception as e:
                    logger.error(f"Error generating value for field {field.get('name', 'unknown')}: {e}")
                    continue
                    
            # Add the completed record to our results
            records.append(record)
            
        # Log success
        if records:
            logger.info(f"Successfully generated {len(records)} records")
            if records[0]:
                logger.debug(f"Sample record: {str(records[0])[:200]}")
        else:
            logger.warning("Generated records list is empty")
            
        return records
    except Exception as e:
        logger.error(f"Error generating records: {e}")
        return []

def generate_field_value(field):
    """
    Generate a value for a field based on its metadata
    
    Args:
        field (dict): Field metadata from Salesforce
        
    Returns:
        Various: Generated value appropriate for the field type and context
    """
    # Safety check - must be a dictionary
    if not isinstance(field, dict):
        return None
        
    # Extract field information safely
    field_type = str(field.get('type', '')).lower()
    field_label = str(field.get('label', '')).lower()
    field_name = str(field.get('name', '')).lower()
    
    # Skip system fields
    system_fields = ['id', 'ownerid', 'createddate', 'createdbyid', 
                     'lastmodifieddate', 'lastmodifiedbyid', 'systemmodstamp',
                     'isdeleted', 'recordtypeid']
    
    if field_name in system_fields:
        return None
    
    # Generate value based on field type
    try:
        # Text fields
        if field_type in ('string', 'textarea'):
            return generate_string_value(field)
            
        # Selection fields
        elif field_type == 'picklist':
            return generate_picklist_value(field)
            
        elif field_type == 'multipicklist':
            return generate_multipicklist_value(field)
            
        # Boolean fields
        elif field_type == 'boolean':
            positive_terms = ['active', 'enabled', 'current', 'approved', 'verified']
            negative_terms = ['inactive', 'disabled', 'canceled', 'rejected', 'deleted']
            
            if any(term in field_name for term in positive_terms):
                return random.choices([True, False], weights=[0.7, 0.3])[0]
            elif any(term in field_name for term in negative_terms):
                return random.choices([True, False], weights=[0.3, 0.7])[0]
            else:
                return random.choice([True, False])
                
        # Number fields
        elif field_type in ('double', 'percent', 'currency'):
            precision = field.get('precision', 18)
            scale = field.get('scale', 2)
            
            # Generate a reasonable number based on field name/label
            min_val = 0
            max_val = 100
            
            if any(term in field_name for term in ['amount', 'price', 'cost', 'revenue']):
                min_val = 10
                max_val = 1000
            elif 'percent' in field_name or field_type == 'percent':
                min_val = 0
                max_val = 100
            elif any(term in field_name for term in ['quantity', 'count', 'number']):
                min_val = 1
                max_val = 50
            
            # Generate a random value with appropriate scale
            value = round(random.uniform(min_val, max_val), scale)
            
            # Handle special numeric fields with specific ranges
            if field_name == 'billinglatitude' or field_name == 'shippinglatitude':
                # Latitude must be between -90 and +90
                value = round(random.uniform(-90, 90), 6)
            elif field_name == 'billinglongitude' or field_name == 'shippinglongitude':
                # Longitude must be between -180 and +180
                value = round(random.uniform(-180, 180), 6)
                
            return value
            
        # Integer fields
        elif field_type == 'int':
            min_val = 0
            max_val = 100
            
            if any(term in field_name for term in ['quantity', 'count', 'number']):
                min_val = 1
                max_val = 50
            elif 'year' in field_name:
                min_val = datetime.now().year - 5
                max_val = datetime.now().year + 5
            
            return random.randint(min_val, max_val)
            
        # Reference fields
        elif field_type == 'reference':
            reference_to = field.get('referenceTo', [])
            if not reference_to or not isinstance(reference_to, list):
                return None
                
            # Default ID patterns for common objects
            ref_object = reference_to[0] if reference_to else ''
            field_name_lower = field_name.lower()
            
            # Handle special fields that need specific ID formats
            if 'dandbcompanyid' in field_name_lower:
                # D&B Company IDs should be null rather than placeholder IDs
                return None
                
            # Standard ID mapping for common objects    
            id_map = {
                'Account': '001000000000001AAA',
                'Contact': '003000000000001AAA',
                'Opportunity': '006000000000001AAA',
                'Lead': '00Q000000000001AAA',
                'Case': '500000000000001AAA',
                'User': '005000000000001AAA'
            }
            
            return id_map.get(ref_object, 'a00000000000001AAA')
            
        # Date fields
        elif field_type == 'date':
            if any(term in field_name for term in ['birth', 'dob']):
                return fake.date_between(start_date='-80y', end_date='-18y').isoformat()
            elif any(term in field_name for term in ['expiry', 'expiration', 'end']):
                return fake.date_between(start_date='today', end_date='+3y').isoformat()
            elif any(term in field_name for term in ['start', 'begin']):
                return fake.date_between(start_date='-30d', end_date='+90d').isoformat()
            elif 'due' in field_name:
                return fake.date_between(start_date='today', end_date='+60d').isoformat()
            else:
                return fake.date_between(start_date='-1y', end_date='+1y').isoformat()
        
        # Datetime fields
        elif field_type == 'datetime':
            if any(term in field_name for term in ['created', 'registered']):
                return fake.date_time_between(start_date='-1y', end_date='now').isoformat()
            elif any(term in field_name for term in ['modified', 'updated']):
                return fake.date_time_between(start_date='-3m', end_date='now').isoformat()
            else:
                return fake.date_time_between(start_date='-1y', end_date='+1y').isoformat()
                
        # Email fields
        elif field_type == 'email':
            return fake.email()
            
        # Phone fields
        elif field_type == 'phone':
            return fake.phone_number()
            
        # URL fields
        elif field_type == 'url':
            return fake.url()
            
        # Default case - return None for unsupported field types
        else:
            return None
    
    except Exception as e:
        logger.error(f"Error generating value for field {field_name} of type {field_type}: {e}")
        return None

def generate_string_value(field):
    """Generate a value for a string field based on its metadata"""
    if not isinstance(field, dict):
        return None
        
    field_name = str(field.get('name', '')).lower()
    field_label = str(field.get('label', '')).lower()
    max_length = field.get('length', 255)
    
    # Email fields
    if 'email' in field_name or 'email' in field_label:
        return fake.email()
        
    # Name fields
    elif field_name == 'name' or field_label == 'name':
        if max_length > 30:
            return fake.company() if 'account' in field_label.lower() else fake.name()
        else:
            return fake.name()[:max_length]
            
    # First/last name fields
    elif 'first' in field_name or 'firstname' in field_name:
        return fake.first_name()
    elif 'last' in field_name or 'lastname' in field_name:
        return fake.last_name()
        
    # Address fields
    elif 'street' in field_name or 'address' in field_name and 'line' in field_name:
        return fake.street_address()
    elif 'city' in field_name:
        return fake.city()
    elif 'state' in field_name:
        return fake.state()
    elif 'country' in field_name:
        return fake.country()
    elif 'zip' in field_name or 'postal' in field_name:
        return fake.zipcode()
        
    # Phone fields
    elif 'phone' in field_name:
        return fake.phone_number()
        
    # URL fields
    elif 'url' in field_name or 'website' in field_name:
        return fake.url()
        
    # Description/comments fields
    elif any(term in field_name for term in ['desc', 'description', 'comment', 'notes']):
        words = min(max_length // 5, 25)  # Estimate words based on max length
        return fake.text(max_nb_chars=max_length)
        
    # Title/subject fields
    elif any(term in field_name for term in ['title', 'subject']):
        return fake.sentence()[:max_length]
        
    # Default case - generate a short phrase
    else:
        return fake.word()[:max_length]

def generate_picklist_value(field):
    """Generate a random value from a picklist field"""
    if not isinstance(field, dict):
        return None
        
    # Extract picklist values
    picklist_values = field.get('picklistValues', [])
    
    # Ensure picklist_values is a list
    if not isinstance(picklist_values, list):
        return None
        
    # Filter to only active values
    active_values = []
    for pv in picklist_values:
        if isinstance(pv, dict) and pv.get('active', True):
            value = pv.get('value')
            if value is not None:
                active_values.append(value)
    
    # If no active values, return None
    if not active_values:
        return None
        
    # Return a random active value
    return random.choice(active_values)

def generate_multipicklist_value(field):
    """Generate a random set of values from a multi-select picklist field"""
    if not isinstance(field, dict):
        return None
        
    # Extract picklist values
    picklist_values = field.get('picklistValues', [])
    
    # Ensure picklist_values is a list
    if not isinstance(picklist_values, list):
        return None
        
    # Filter to only active values
    active_values = []
    for pv in picklist_values:
        if isinstance(pv, dict) and pv.get('active', True):
            value = pv.get('value')
            if value is not None:
                active_values.append(value)
    
    # If no active values, return None
    if not active_values:
        return None
        
    # Determine how many values to select (1-3, but not more than available)
    count = min(random.randint(1, 3), len(active_values))
    
    # Select random values
    selected = random.sample(active_values, count)
    
    # Join with semicolons
    return ';'.join(selected)

def analyze_schema(object_info):
    """
    Analyze a Salesforce schema to identify patterns and constraints
    
    Args:
        object_info (dict or str): Object schema information from Salesforce
        
    Returns:
        dict: Analysis of the schema
    """
    # Normalize object_info to a dictionary
    if isinstance(object_info, str):
        try:
            object_info = json.loads(object_info)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON string provided"}
            
    if not isinstance(object_info, dict):
        return {"error": f"Expected dictionary, got {type(object_info)}"}
        
    # Extract fields
    fields = object_info.get('fields', [])
    if not isinstance(fields, list):
        return {"error": "Fields is not a list"}
        
    # Initialize analysis
    analysis = {
        "object_name": object_info.get('name', 'Unknown'),
        "total_fields": len(fields),
        "required_fields": [],
        "reference_fields": [],
        "picklist_fields": [],
        "field_types": {},
        "unique_fields": []
    }
    
    # Analyze each field
    for field in fields:
        if not isinstance(field, dict):
            continue
            
        field_name = field.get('name')
        field_type = field.get('type')
        
        if not field_name or not field_type:
            continue
            
        # Track field types
        if field_type not in analysis["field_types"]:
            analysis["field_types"][field_type] = 0
        analysis["field_types"][field_type] += 1
        
        # Track required fields
        if field.get('nillable') is False and not field.get('defaultedOnCreate', False):
            analysis["required_fields"].append(field_name)
            
        # Track unique fields
        if field.get('unique', False):
            analysis["unique_fields"].append(field_name)
            
        # Track reference fields
        if field_type == 'reference' and field.get('referenceTo'):
            analysis["reference_fields"].append({
                "name": field_name,
                "references": field.get('referenceTo')
            })
            
        # Track picklist fields
        if field_type in ('picklist', 'multipicklist') and field.get('picklistValues'):
            analysis["picklist_fields"].append({
                "name": field_name,
                "values": [pv.get('value') for pv in field.get('picklistValues', []) 
                           if isinstance(pv, dict) and pv.get('active', True)]
            })
    
    return analysis
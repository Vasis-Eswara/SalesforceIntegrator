"""
Utilities for generating test data using Faker
"""
import json
import random
import logging
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
    
    # Count createable fields with additional error handling and detailed logging
    createable_fields = []
    
    # Check if fields is iterable
    if not isinstance(fields, list):
        logger.error(f"Fields is not a list, it's a {type(fields)}")
        # Dump fields content for debugging
        try:
            logger.error(f"Fields content: {str(fields)[:200]}...")
        except Exception as e:
            logger.error(f"Could not print fields content: {e}")
        
        # Try to convert non-list fields to list if it's a string
        if isinstance(fields, str):
            try:
                logger.warning("Attempting to parse string fields as JSON")
                fields = json.loads(fields)
                if isinstance(fields, list):
                    logger.info(f"Successfully converted string fields to list with {len(fields)} items")
                else:
                    logger.error(f"Parsed fields is not a list: {type(fields)}")
                    fields = []
            except Exception as e:
                logger.error(f"Failed to parse fields string as JSON: {e}")
                fields = []
        else:
            fields = []
    
    logger.debug(f"Processing {len(fields)} fields for createable check")
    
    for i, f in enumerate(fields):
        # Verify each field is a dictionary to avoid 'str' object has no attribute 'get' error
        if not isinstance(f, dict):
            logger.error(f"Field at index {i} is not a dictionary, it's a {type(f)}: {str(f)[:100]}")
            
            # Try to convert string to dict if it's a JSON string
            if isinstance(f, str):
                try:
                    logger.warning(f"Attempting to parse string field at index {i} as JSON")
                    f = json.loads(f)
                    if isinstance(f, dict):
                        logger.info(f"Successfully converted string field to dictionary at index {i}")
                    else:
                        logger.error(f"Parsed field is not a dictionary: {type(f)}")
                        continue
                except Exception as e:
                    logger.error(f"Failed to parse field string as JSON at index {i}: {e}")
                    continue
            else:
                continue
        
        # Check if field is createable
        try:
            if f.get('createable', True):
                createable_fields.append(f)
        except Exception as e:
            logger.error(f"Error checking if field is createable: {e}, field: {str(f)[:100]}")
    
    # Extra safeguard - dump the first few fields for debugging
    if fields and len(fields) > 0:
        try:
            sample_field = fields[0]
            logger.debug(f"Sample field (first in list): {sample_field}")
            logger.debug(f"Sample field type: {type(sample_field)}")
            if isinstance(sample_field, dict):
                logger.debug(f"Sample field keys: {list(sample_field.keys())}")
        except Exception as e:
            logger.error(f"Error examining sample field: {e}")
            
    logger.info(f"Preparing to generate {record_count} records with {len(createable_fields)} createable fields out of {len(fields)} total fields")
    records = []
    
    # First, identify required fields and any field dependencies
    required_fields = []
    relationship_fields = {}
    picklist_fields = {}
    
    for field in fields:
        # Skip non-dictionary fields 
        if not isinstance(field, dict):
            logger.error(f"Field is not a dictionary, it's a {type(field)}: {field}")
            continue
            
        # Skip fields that can't be created via API
        try:
            if not field.get('createable', True):
                continue
        except Exception as e:
            logger.error(f"Error checking if field is createable: {e}, field: {field}")
            continue
            
        try:
            if field.get('nillable') is False and not field.get('defaultedOnCreate', False):
                required_fields.append(field)
        except Exception as e:
            logger.error(f"Error checking if field is required: {e}, field: {field}")
            continue
            
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
            # Skip non-dictionary fields
            if not isinstance(field, dict):
                logger.error(f"Field is not a dictionary, it's a {type(field)}: {field}")
                continue
                
            try:
                field_name = field.get('name')
                field_type = field.get('type')
                
                # Skip fields without a name
                if not field_name:
                    logger.warning(f"Field has no name: {field}")
                    continue
                
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
                    
            except Exception as e:
                logger.error(f"Error processing field for data generation: {e}, field: {field}")
                continue
        
        records.append(record)
    
    # Return generated records
    return records

def generate_field_value(field):
    """
    Generate a value for a field based on its metadata with enhanced intelligence
    
    Args:
        field (dict): Field metadata from Salesforce
        
    Returns:
        Various: Generated value appropriate for the field type and context
    """
    import logging
    logger = logging.getLogger(__name__)
    import string
    
    # Safeguard against non-dict fields
    if not isinstance(field, dict):
        logger.error(f"Field is not a dictionary: {type(field)}")
        return None
        
    # Extract field information safely
    try:
        field_type = str(field.get('type', '')).lower()
        field_label = str(field.get('label', '')).lower()
        field_name = str(field.get('name', '')).lower()
    except Exception as e:
        logger.error(f"Error extracting field properties: {e}")
        field_type = ''
        field_label = ''
        field_name = ''
    
    # Log field info at debug level
    logger.debug(f"Generating value for field: {field_name}, type: {field_type}, label: {field_label}")
    
    # Skip system fields
    system_fields = ['id', 'ownerid', 'createddate', 'createdbyid', 
                     'lastmodifieddate', 'lastmodifiedbyid', 'systemmodstamp',
                     'isdeleted', 'recordtypeid']
    
    if field_name.lower() in system_fields:
        logger.debug(f"Skipping system field: {field_name}")
        return None
    
    # Handle specific field contexts based on the combination of field type, name and label
    try:
        # Text fields with specialized generation
        if field_type in ('string', 'textarea'):
            return generate_string_value(field)
            
        # Selection fields with predefined options
        elif field_type == 'picklist':
            return generate_picklist_value(field)
            
        elif field_type == 'multipicklist':
            return generate_multipicklist_value(field)
            
        # Boolean fields with contextual weighting
        elif field_type == 'boolean':
            # Check for fields that are more likely to be true or false based on name/label
            positive_indicators = ['active', 'enabled', 'is_current', 'approved', 'verified', 'primary', 'completed']
            negative_indicators = ['inactive', 'disabled', 'canceled', 'rejected', 'deleted', 'archived']
            
            if any(term in field_name for term in positive_indicators):
                # 70% chance of being True for fields like "IsActive"
                return random.choices([True, False], weights=[0.7, 0.3])[0]
            elif any(term in field_name for term in negative_indicators):
                # 30% chance of being True for fields like "IsCanceled"
                return random.choices([True, False], weights=[0.3, 0.7])[0]
            else:
                # Default equal weighting
                return random.choice([True, False])
            
        # Reference fields with intelligent placeholders
        elif field_type == 'reference':
            # Different placeholder IDs based on the referenced object type
            reference_to = field.get('referenceTo', [])
            if not reference_to or not isinstance(reference_to, list):
                return None
            
            ref_object = reference_to[0] if reference_to else ''
            
            # Generate appropriate placeholder IDs based on common object prefixes
            if ref_object == 'Account':
                return '001000000000001AAA'
            elif ref_object == 'Contact':
                return '003000000000001AAA'
            elif ref_object == 'Opportunity':
                return '006000000000001AAA'
            elif ref_object == 'Lead':
                return '00Q000000000001AAA'
            elif ref_object == 'Case':
                return '500000000000001AAA'
            elif ref_object == 'User':
                return '005000000000001AAA'
            else:
                # Generic placeholder for other objects
                return 'a00000000000001AAA'
            
        # Date fields with contextual date ranges
        elif field_type == 'date':
            # Adjust date ranges based on field semantic meaning
            if any(term in field_name for term in ['birth', 'dob']):
                # Birth dates typically range from 18-80 years ago
                return fake.date_between(start_date='-80y', end_date='-18y').isoformat()
                
            elif any(term in field_name for term in ['expiry', 'expiration', 'end']):
                # Expiration dates are usually in the future
                return fake.date_between(start_date='today', end_date='+3y').isoformat()
                
            elif any(term in field_name for term in ['start', 'begin', 'commencement']):
                # Start dates can be recently in past or near future
                return fake.date_between(start_date='-30d', end_date='+90d').isoformat()
                
            elif 'due' in field_name:
                # Due dates are typically in the near future
                return fake.date_between(start_date='today', end_date='+60d').isoformat()
                
            elif 'created' in field_name or 'registered' in field_name:
                # Creation dates in the past
                return fake.date_between(start_date='-2y', end_date='today').isoformat()
                
            else:
                # Default date range
                return fake.date_between(start_date='-2y', end_date='+1y').isoformat()
                
        # Datetime fields with appropriate time components
        elif field_type == 'datetime':
            # Similar patterns as date fields
            if any(term in field_name for term in ['created', 'registered']):
                # Creation dates typically in the past
                return fake.date_time_between(start_date='-2y', end_date='now').isoformat()
                
            elif any(term in field_name for term in ['modified', 'updated', 'last']):
                # Last modified usually recent
                return fake.date_time_between(start_date='-3m', end_date='now').isoformat()
                
            elif any(term in field_name for term in ['scheduled', 'appointment', 'meeting']):
                # Scheduled times usually in future business hours
                future_date = fake.date_time_between(start_date='+1d', end_date='+60d')
                # Adjust hour to business hours (9am-5pm)
                business_hour = random.randint(9, 17)
                future_date = future_date.replace(hour=business_hour, minute=random.choice([0, 15, 30, 45]))
                return future_date.isoformat()
                
            else:
                # Default datetime range
                return fake.date_time_between(start_date='-2y', end_date='+1y').isoformat()
                
        # Time fields
        elif field_type == 'time':
            if any(term in field_name for term in ['start', 'begin']):
                # Business start times typically in the morning
                hour = random.randint(8, 10)
                minute = random.choice([0, 15, 30, 45])
                return f"{hour:02d}:{minute:02d}:00.000Z"
                
            elif any(term in field_name for term in ['end', 'finish', 'close']):
                # Business end times typically in the afternoon
                hour = random.randint(16, 18)
                minute = random.choice([0, 15, 30, 45])
                return f"{hour:02d}:{minute:02d}:00.000Z"
                
            else:
                # Standard business hours as default
                hour = random.randint(9, 17)
                minute = random.choice([0, 15, 30, 45])
                return f"{hour:02d}:{minute:02d}:00.000Z"
                
        # Integer fields with semantic ranges
        elif field_type == 'int':
            try:
                # Start with default range
                min_val = 0
                max_val = 100
                
                # Try to get field-defined constraints
                min_value = field.get('minValue')
                if min_value is not None:
                    try:
                        min_val = int(min_value)
                    except (ValueError, TypeError):
                        pass
                        
                max_value = field.get('maxValue')
                if max_value is not None:
                    try:
                        max_val = int(max_value)
                    except (ValueError, TypeError):
                        pass
                        
                # Ensure min is less than max
                if min_val >= max_val:
                    min_val = 0
                    max_val = 100
                    
                # Adjust ranges for common field semantics
                if any(term in field_name for term in ['quantity', 'count', 'amount', 'number']):
                    min_val = max(0, min_val)  # Non-negative for counts
                    if 'large' in field_name or 'bulk' in field_name:
                        max_val = max(max_val, 1000)
                    
                if 'age' in field_name:
                    min_val = max(0, min_val)
                    max_val = min(120, max_val)  # Reasonable age limit
                    
                if 'year' in field_name:
                    current_year = datetime.now().year
                    if 'birth' in field_name or 'founded' in field_name:
                        min_val = max(current_year - 100, min_val)
                        max_val = min(current_year, max_val)
                    else:
                        min_val = max(current_year - 10, min_val)
                        max_val = min(current_year + 10, max_val)
                        
                if 'priority' in field_name:
                    min_val = max(1, min_val)
                    max_val = min(5, max_val)
                    
                # Limit to reasonable maximum to prevent issues
                max_val = min(max_val, 1000000)
                    
                return random.randint(min_val, max_val)
            except Exception as e:
                logger.error(f"Error generating integer value: {e}")
                return random.randint(0, 100)  # Fallback
            
        # Decimal fields with appropriate scale and precision
        elif field_type in ('double', 'currency', 'percent'):
            try:
                # Start with default range
                min_val = 0.0
                max_val = 100.0
                scale = 2  # Default decimal places
                
                # Try to get field-defined constraints
                min_value = field.get('minValue')
                if min_value is not None:
                    try:
                        min_val = float(min_value)
                    except (ValueError, TypeError):
                        pass
                        
                max_value = field.get('maxValue')
                if max_value is not None:
                    try:
                        max_val = float(max_value)
                    except (ValueError, TypeError):
                        pass
                        
                # Get precision settings if available
                scale_value = field.get('scale')
                if scale_value is not None:
                    try:
                        scale = min(int(scale_value), 10)  # Limit to 10 decimal places
                        scale = max(0, scale)  # Ensure non-negative
                    except (ValueError, TypeError):
                        pass
                
                # Ensure min is less than max
                if min_val >= max_val:
                    min_val = 0.0
                    max_val = 100.0
                    
                # Adjust ranges based on field type
                if field_type == 'percent':
                    min_val = max(0.0, min_val)
                    max_val = min(100.0, max_val)
                    
                # Adjust ranges for common field semantics
                if field_type == 'currency':
                    if any(term in field_name for term in ['price', 'cost']):
                        if 'wholesale' in field_name:
                            min_val = max(0.01, min_val)
                            max_val = min(500.0, max_val)
                        elif 'premium' in field_name or 'luxury' in field_name:
                            min_val = max(10.0, min_val)
                            max_val = min(5000.0, max_val)
                            
                if 'discount' in field_name:
                    min_val = max(0.0, min_val)
                    max_val = min(50.0, max_val)
                    
                if 'rating' in field_name:
                    min_val = max(0.0, min_val)
                    max_val = min(5.0, max_val)
                    scale = min(1, scale)  # Usually 1 decimal place for ratings
                    
                # Limit to reasonable maximum to prevent issues
                max_val = min(max_val, 1000000.0)
                
                # Generate value with appropriate precision
                value = random.uniform(min_val, max_val)
                return round(value, scale)
            except Exception as e:
                logger.error(f"Error generating decimal value: {e}")
                return round(random.uniform(0, 100), 2)  # Fallback
            
        # Contact information fields
        elif field_type == 'phone':
            if 'fax' in field_name:
                return fake.phone_number()
            elif 'mobile' in field_name or 'cell' in field_name:
                return fake.phone_number()
            elif 'work' in field_name or 'office' in field_name:
                return fake.phone_number()
            else:
                return fake.phone_number()
                
        elif field_type == 'email':
            company_domains = ['example.com', 'acme.org', 'globex.net', 'initech.io', 'umbrella.co']
            
            if 'work' in field_name or 'business' in field_name:
                username = fake.user_name()
                domain = random.choice(company_domains)
                return f"{username}@{domain}"
            elif 'personal' in field_name:
                return fake.free_email()
            else:
                return fake.email()
                
        elif field_type == 'url':
            if 'linkedin' in field_name:
                return f"https://www.linkedin.com/in/{fake.user_name()}"
            elif 'twitter' in field_name or 'x' in field_name:
                return f"https://twitter.com/{fake.user_name()}"
            elif 'facebook' in field_name:
                return f"https://www.facebook.com/{fake.user_name()}"
            elif 'website' in field_name or 'site' in field_name or 'web' in field_name:
                return f"https://www.{fake.domain_name()}"
            else:
                return fake.uri()
                
        elif field_type == 'address':
            # Return compound address as string
            address = fake.address()
            return address.replace('\n', ', ')
            
        # Additional data types
        elif field_type == 'base64':
            # Simple base64 placeholder
            return 'U2FtcGxlIEJhc2U2NCBEYXRh'
            
        elif field_type == 'location' or field_type == 'geolocation':
            # Return a dict or string with coordinates
            lat = round(float(fake.latitude()), 6)
            lng = round(float(fake.longitude()), 6)
            return f"{lat},{lng}"
            
        # Fallback for unhandled types
        logger.debug(f"Unhandled field type: {field_type}")
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error in generate_field_value: {e}")
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
        # Skip non-dictionary fields
        if not isinstance(field, dict):
            logger.error(f"Field is not a dictionary, it's a {type(field)}: {field}")
            continue
            
        try:
            field_name = field.get('name')
            
            # Skip fields without a name
            if not field_name:
                logger.warning(f"Skipping field without a name: {field}")
                continue
            
            # Track required fields
            try:
                if not field.get('nillable') and not field.get('defaultedOnCreate'):
                    analysis['requiredFields'].append({
                        'name': field_name,
                        'label': field.get('label'),
                        'type': field.get('type')
                    })
            except Exception as e:
                logger.error(f"Error processing required field: {e}, field: {field_name}")
                
            # Track unique fields
            try:
                if field.get('unique'):
                    analysis['uniqueFields'].append({
                        'name': field_name,
                        'label': field.get('label'),
                        'type': field.get('type')
                    })
            except Exception as e:
                logger.error(f"Error processing unique field: {e}, field: {field_name}")
                
            # Track picklist fields
            try:
                if field.get('type') == 'picklist' and field.get('picklistValues'):
                    picklist_values = field.get('picklistValues')
                    if not isinstance(picklist_values, list):
                        logger.warning(f"picklistValues is not a list for field {field_name}")
                        continue
                        
                    valid_values = []
                    for pv in picklist_values:
                        if not isinstance(pv, dict):
                            logger.warning(f"Picklist value is not a dictionary: {pv}")
                            continue
                        
                        if pv.get('active', True) and pv.get('value') is not None:
                            valid_values.append(pv.get('value'))
                    
                    analysis['picklistFields'][field_name] = {
                        'label': field.get('label'),
                        'values': valid_values
                    }
            except Exception as e:
                logger.error(f"Error processing picklist field: {e}, field: {field_name}")
                
            # Track reference fields
            try:
                if field.get('type') == 'reference' and field.get('referenceTo'):
                    references = field.get('referenceTo')
                    if not isinstance(references, list):
                        logger.warning(f"referenceTo is not a list for field {field_name}")
                        references = [str(references)] if references else []
                        
                    analysis['referenceFields'][field_name] = {
                        'label': field.get('label'),
                        'referencesTo': references
                    }
            except Exception as e:
                logger.error(f"Error processing reference field: {e}, field: {field_name}")
                
        except Exception as e:
            logger.error(f"Error analyzing field: {e}, field: {field}")
            continue
    
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
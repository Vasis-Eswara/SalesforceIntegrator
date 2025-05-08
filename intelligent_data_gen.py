"""
Intelligent data generation for Salesforce objects
This module provides a smarter approach to generating test data for Salesforce
that respects field dependencies, validation rules, and existing data patterns.
"""
import json
import random
import logging
import re
from datetime import datetime, timedelta
from faker import Faker

# Initialize the Faker generator
fake = Faker()
logger = logging.getLogger(__name__)

class IntelligentDataGenerator:
    """
    Intelligent data generator that uses Salesforce schema, existing data,
    and field relationships to create valid test records.
    """
    
    def __init__(self, sf_connection):
        """
        Initialize the generator with a Salesforce connection
        
        Args:
            sf_connection: Object with access_token and instance_url for API calls
        """
        self.sf_connection = sf_connection
        self.cache = {
            'record_ids': {},   # Cache of record IDs by object type
            'field_values': {}, # Cache of valid field values by object and field
            'object_metadata': {} # Cache of object metadata
        }
        
        # Get API version dynamically instead of hardcoding
        self.api_version = self._detect_api_version() or "v58.0"
        logger.info(f"Using Salesforce API version: {self.api_version}")
        
    def _detect_api_version(self):
        """Detect the latest available API version for this org"""
        try:
            import requests
            
            headers = {
                'Authorization': f'Bearer {self.sf_connection.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Get available versions
            url = f"{self.sf_connection.instance_url}/services/data/"
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                versions = response.json()
                if versions and isinstance(versions, list) and len(versions) > 0:
                    # Sort versions and get the latest
                    latest = sorted(versions, key=lambda v: v.get('version', '0'), reverse=True)[0]
                    return f"v{latest.get('version')}"
            
            return None
        except Exception as e:
            logger.error(f"Error detecting API version: {e}")
            return None
        
    def generate_data(self, object_name, record_count=5, existing_records=None):
        """
        Generate valid test data for a Salesforce object
        
        Args:
            object_name (str): API name of the Salesforce object
            record_count (int): Number of records to generate
            existing_records (list): Optional list of existing records to use as a pattern
            
        Returns:
            dict: Dictionary with generation results including records, errors, and counts
        """
        logger.info(f"Intelligently generating {record_count} records for {object_name}")
        
        # Get object metadata if not cached
        if object_name not in self.cache['object_metadata']:
            self._fetch_object_metadata(object_name)
            
        # Get valid record IDs for lookup fields
        self._prepare_lookup_data(object_name)
        
        # Generate records
        records = []
        errors = []
        
        # Use existing records as a base pattern if provided
        pattern = self._analyze_patterns(object_name, existing_records)
        
        # Check if this is likely a brand new org with no data
        is_empty_org = not self.cache['record_ids'] or all(len(ids) == 0 for ids in self.cache['record_ids'].values())
        
        if is_empty_org:
            logger.warning(f"No existing records found in org for reference. Using basic generation for {object_name}")
            
            # Add extra logging/warning in the error list but don't prevent generation
            errors.append(f"Note: No existing records found to analyze. Using basic generation patterns for {object_name}.")
        
        # Generate the requested number of records
        for i in range(record_count):
            try:
                record = self._generate_single_record(object_name, pattern)
                records.append(record)
                logger.debug(f"Generated record {i+1}/{record_count} for {object_name}")
            except Exception as e:
                logger.error(f"Error generating record {i+1}: {e}")
                errors.append(str(e))
                
        # Return the generated records and any errors
        return {
            "records": records,
            "errors": errors,
            "success_count": len(records),
            "error_count": len(errors),
            "is_empty_org": is_empty_org
        }
    
    def _fetch_object_metadata(self, object_name):
        """
        Fetch and cache metadata for a Salesforce object
        
        Args:
            object_name (str): API name of the Salesforce object
        """
        logger.info(f"Fetching metadata for {object_name}")
        
        try:
            # Make API call to get object metadata
            import requests
            
            headers = {
                'Authorization': f'Bearer {self.sf_connection.access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.sf_connection.instance_url}/services/data/{self.api_version}/sobjects/{object_name}/describe/"
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            metadata = response.json()
            
            # Process field metadata to make it more useful
            fields = {}
            for field in metadata.get('fields', []):
                fields[field['name']] = field
            
            # Store processed metadata in cache
            self.cache['object_metadata'][object_name] = {
                'label': metadata.get('label'),
                'fields': fields,
                'recordTypeInfos': metadata.get('recordTypeInfos', []),
                'childRelationships': metadata.get('childRelationships', []),
                'createable': metadata.get('createable', False),
                'required_fields': [f['name'] for f in metadata.get('fields', []) 
                                  if not f.get('nillable', True) and not f.get('defaultedOnCreate', False)]
            }
            
            logger.info(f"Successfully cached metadata for {object_name} with {len(fields)} fields")
            
        except Exception as e:
            logger.error(f"Error fetching metadata for {object_name}: {e}")
            # Initialize with empty metadata to avoid repeated failures
            self.cache['object_metadata'][object_name] = {
                'fields': {},
                'required_fields': []
            }
    
    def _prepare_lookup_data(self, object_name):
        """
        Fetch and cache record IDs for lookup fields in the object
        
        Args:
            object_name (str): API name of the Salesforce object
        """
        # Skip if metadata isn't available
        if not self.cache['object_metadata'].get(object_name, {}).get('fields'):
            return
            
        # Find reference fields that need valid IDs
        reference_fields = {}
        
        for field_name, field in self.cache['object_metadata'][object_name]['fields'].items():
            if field.get('type') == 'reference' and field.get('referenceTo'):
                for ref_object in field.get('referenceTo', []):
                    if ref_object not in reference_fields:
                        reference_fields[ref_object] = []
                    reference_fields[ref_object].append(field_name)
        
        # Fetch IDs for reference objects if not already cached
        for ref_object, fields in reference_fields.items():
            if ref_object not in self.cache['record_ids']:
                self._fetch_record_ids(ref_object)
    
    def _fetch_record_ids(self, object_name, limit=20):
        """
        Fetch and cache record IDs for an object to use for reference fields
        
        Args:
            object_name (str): API name of the Salesforce object
            limit (int): Maximum number of IDs to fetch
        """
        logger.info(f"Fetching record IDs for {object_name}")
        
        try:
            # Make API call to get record IDs
            import requests
            
            headers = {
                'Authorization': f'Bearer {self.sf_connection.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Query for IDs only to minimize data transfer
            url = f"{self.sf_connection.instance_url}/services/data/{self.api_version}/query/"
            params = {
                'q': f"SELECT Id FROM {object_name} ORDER BY CreatedDate DESC LIMIT {limit}"
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 403:
                # User doesn't have access to the object
                logger.warning(f"Object-level security prevents access to {object_name}. Using basic generation.")
                self.cache['record_ids'][object_name] = []
                return
            elif response.status_code == 404:
                # Object doesn't exist
                logger.warning(f"Object {object_name} not found. It may not exist or be available in this org.")
                self.cache['record_ids'][object_name] = []
                return
            elif response.status_code >= 400:
                # Other API error
                logger.warning(f"Could not fetch records for {object_name}. API error: {response.status_code}")
                self.cache['record_ids'][object_name] = []
                return
                
            response.raise_for_status()
            
            data = response.json()
            
            # Extract IDs from response
            ids = [record['Id'] for record in data.get('records', [])]
            
            # Cache the IDs
            self.cache['record_ids'][object_name] = ids
            
            logger.info(f"Cached {len(ids)} record IDs for {object_name}")
            
        except Exception as e:
            logger.error(f"Error fetching record IDs for {object_name}: {e}")
            # Initialize with empty list to avoid repeated failures
            self.cache['record_ids'][object_name] = []
    
    def _fetch_field_values(self, object_name, field_name, limit=20):
        """
        Fetch and cache valid values for a field to use for generation
        
        Args:
            object_name (str): API name of the Salesforce object
            field_name (str): API name of the field
            limit (int): Maximum number of values to fetch
        """
        field_key = f"{object_name}.{field_name}"
        
        if field_key in self.cache['field_values']:
            return
            
        logger.info(f"Fetching valid values for {field_key}")
        
        try:
            # Make API call to get field values
            import requests
            
            headers = {
                'Authorization': f'Bearer {self.sf_connection.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Query for values
            url = f"{self.sf_connection.instance_url}/services/data/{self.api_version}/query/"
            params = {
                'q': f"SELECT {field_name} FROM {object_name} WHERE {field_name} != null LIMIT {limit}"
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 403:
                # User doesn't have field-level access
                logger.warning(f"Field-level security prevents access to {field_key}. Using basic generation.")
                self.cache['field_values'][field_key] = []
                return
            elif response.status_code >= 400:
                # Field may not exist or other issue
                logger.warning(f"Could not fetch values for {field_key}. Field may not exist or API error: {response.status_code}")
                self.cache['field_values'][field_key] = []
                return
                
            response.raise_for_status()
            
            data = response.json()
            
            # Extract values from response
            values = [record[field_name] for record in data.get('records', []) if field_name in record]
            
            # Cache the values
            self.cache['field_values'][field_key] = values
            
            logger.info(f"Cached {len(values)} values for {field_key}")
            
        except Exception as e:
            logger.error(f"Error fetching values for {field_key}: {e}")
            # Initialize with empty list to avoid repeated failures
            self.cache['field_values'][field_key] = []
    
    def _analyze_patterns(self, object_name, existing_records=None):
        """
        Analyze existing records to find patterns for data generation
        
        Args:
            object_name (str): API name of the Salesforce object
            existing_records (list): Optional list of existing records to analyze
            
        Returns:
            dict: Patterns discovered in the data
        """
        # Initialize patterns
        patterns = {
            'field_distributions': {},  # Frequency of values for fields
            'field_formats': {},        # Common formats for string fields
            'dependencies': {}          # Field dependencies
        }
        
        # Use provided records or fetch some if needed
        records = existing_records or []
        
        if not records:
            # Try to fetch some records for analysis
            try:
                import requests
                
                headers = {
                    'Authorization': f'Bearer {self.sf_connection.access_token}',
                    'Content-Type': 'application/json'
                }
                
                # Get a sample of records to analyze
                url = f"{self.sf_connection.instance_url}/services/data/{self.api_version}/query/"
                params = {
                    'q': f"SELECT * FROM {object_name} LIMIT 50"
                }
                
                response = requests.get(url, headers=headers, params=params)
                
                if response.status_code == 403:
                    # User doesn't have access to the object
                    logger.warning(f"Object-level security prevents access to {object_name} for pattern analysis. Using basic generation.")
                elif response.status_code == 404:
                    # Object doesn't exist
                    logger.warning(f"Object {object_name} not found for pattern analysis. It may not exist in this org.")
                elif response.status_code == 400:
                    # Query syntax error - probably due to a field not being accessible
                    logger.warning(f"Pattern analysis query error for {object_name}: {response.text[:200]}...")
                    
                    # Try a simpler query with just the ID - often more likely to succeed
                    try:
                        simple_url = f"{self.sf_connection.instance_url}/services/data/{self.api_version}/query/"
                        simple_params = {
                            'q': f"SELECT Id FROM {object_name} LIMIT 1"
                        }
                        
                        simple_response = requests.get(simple_url, headers=headers, params=simple_params)
                        
                        if simple_response.status_code < 400:
                            logger.info(f"Object {object_name} exists but the full query failed. Will use basic generation.")
                    except Exception:
                        pass
                elif response.status_code < 400:
                    data = response.json()
                    records = data.get('records', [])
                    logger.info(f"Fetched {len(records)} records for pattern analysis")
            except Exception as e:
                logger.error(f"Error fetching records for pattern analysis: {e}")
        
        # Analyze records if we have any
        if records:
            self._extract_patterns_from_records(object_name, records, patterns)
            
        return patterns
    
    def _extract_patterns_from_records(self, object_name, records, patterns):
        """
        Extract patterns from a set of records
        
        Args:
            object_name (str): API name of the Salesforce object
            records (list): List of records to analyze
            patterns (dict): Dictionary to store extracted patterns
        """
        # Skip if no records
        if not records:
            return
            
        # Get field metadata
        fields = self.cache['object_metadata'].get(object_name, {}).get('fields', {})
        
        # Loop through all fields in the records
        all_field_names = set()
        for record in records:
            all_field_names.update(record.keys())
            
        # Analyze each field
        for field_name in all_field_names:
            # Skip metadata fields and attributes
            if field_name in ['attributes', 'Id', 'CreatedById', 'CreatedDate', 
                             'LastModifiedById', 'LastModifiedDate', 'SystemModstamp']:
                continue
                
            # Get values for this field
            values = [record.get(field_name) for record in records if field_name in record]
            
            # Skip if no values
            if not values:
                continue
                
            # Analyze non-null values
            non_null_values = [v for v in values if v is not None]
            
            if non_null_values:
                # Calculate distribution of values
                value_counts = {}
                for value in non_null_values:
                    value_counts[value] = value_counts.get(value, 0) + 1
                    
                patterns['field_distributions'][field_name] = value_counts
                
                # Extract string formats if applicable
                if isinstance(non_null_values[0], str):
                    formats = self._extract_string_formats(non_null_values)
                    if formats:
                        patterns['field_formats'][field_name] = formats
        
        # Look for field dependencies
        self._extract_field_dependencies(records, patterns)
    
    def _extract_string_formats(self, values):
        """
        Extract common formats from string values
        
        Args:
            values (list): List of string values
            
        Returns:
            dict: Information about common formats
        """
        formats = {}
        
        # Only analyze a reasonable number of values
        sample = values[:100]
        
        # Check for numeric formats
        numeric_pattern = re.compile(r'^\d+$')
        if all(numeric_pattern.match(v) for v in sample if v):
            formats['type'] = 'numeric'
            formats['lengths'] = list(set(len(v) for v in sample if v))
            return formats
            
        # Check for date formats
        date_patterns = [
            (re.compile(r'^\d{4}-\d{2}-\d{2}$'), 'yyyy-mm-dd'),
            (re.compile(r'^\d{2}/\d{2}/\d{4}$'), 'mm/dd/yyyy'),
            (re.compile(r'^\d{2}-\d{2}-\d{4}$'), 'mm-dd-yyyy')
        ]
        
        for pattern, format_name in date_patterns:
            if all(pattern.match(v) for v in sample if v):
                formats['type'] = 'date'
                formats['format'] = format_name
                return formats
                
        # Check for common patterns
        phone_pattern = re.compile(r'^\(\d{3}\) \d{3}-\d{4}$')
        if all(phone_pattern.match(v) for v in sample if v):
            formats['type'] = 'phone'
            return formats
            
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if all(email_pattern.match(v) for v in sample if v):
            formats['type'] = 'email'
            return formats
            
        # Check for delimited values
        if all(',' in v for v in sample if v):
            formats['type'] = 'csv'
            return formats
            
        if all(';' in v for v in sample if v):
            formats['type'] = 'semicolon_delimited'
            return formats
            
        # Return length information for general strings
        formats['type'] = 'string'
        formats['min_length'] = min(len(v) for v in sample if v)
        formats['max_length'] = max(len(v) for v in sample if v)
        formats['avg_length'] = sum(len(v) for v in sample if v) // len(sample)
        
        return formats
    
    def _extract_field_dependencies(self, records, patterns):
        """
        Identify dependencies between fields
        
        Args:
            records (list): List of records to analyze
            patterns (dict): Dictionary to store extracted patterns
        """
        # Need sufficient records for dependency analysis
        if len(records) < 10:
            return
            
        # Get all field pairs
        field_names = set()
        for record in records:
            field_names.update(k for k in record.keys() if k != 'attributes')
            
        field_pairs = [(f1, f2) for f1 in field_names for f2 in field_names if f1 < f2]
        
        # Check each pair for dependencies
        for field1, field2 in field_pairs:
            # Skip pairs where one field is often null
            values1 = [record.get(field1) for record in records if field1 in record]
            values2 = [record.get(field2) for record in records if field2 in record]
            
            non_null1 = [v for v in values1 if v is not None]
            non_null2 = [v for v in values2 if v is not None]
            
            if len(non_null1) < len(values1) * 0.7 or len(non_null2) < len(values2) * 0.7:
                continue
                
            # Check for patterns between fields
            pairs = [(record.get(field1), record.get(field2)) 
                    for record in records 
                    if field1 in record and field2 in record 
                    and record.get(field1) is not None 
                    and record.get(field2) is not None]
                    
            # Check if certain values in field1 always correspond to certain values in field2
            if len(pairs) >= 10:
                field1_to_field2 = {}
                
                for val1, val2 in pairs:
                    if val1 not in field1_to_field2:
                        field1_to_field2[val1] = set()
                    field1_to_field2[val1].add(val2)
                    
                # If field1 value usually corresponds to a single field2 value, record the dependency
                strong_dependencies = {}
                
                for val1, val2_set in field1_to_field2.items():
                    if len(val2_set) == 1:
                        strong_dependencies[val1] = next(iter(val2_set))
                        
                if strong_dependencies and len(strong_dependencies) >= 3:
                    patterns['dependencies'][f"{field1}→{field2}"] = strong_dependencies
    
    def _generate_single_record(self, object_name, pattern=None):
        """
        Generate a single valid record for a Salesforce object
        
        Args:
            object_name (str): API name of the Salesforce object
            pattern (dict): Optional patterns to follow for generation
            
        Returns:
            dict: Generated record
        """
        # Get object metadata
        metadata = self.cache['object_metadata'].get(object_name, {})
        fields = metadata.get('fields', {})
        
        # Initialize record
        record = {}
        
        # First pass: Handle standard fields and those with defined patterns
        for field_name, field in fields.items():
            # Skip auto-generated or system fields
            if (field.get('autoNumber', False) or
                field.get('calculated', False) or
                not field.get('createable', True) or
                field_name in ['Id', 'CreatedDate', 'CreatedById', 'LastModifiedDate', 
                              'LastModifiedById', 'SystemModstamp', 'IsDeleted']):
                continue
                
            # Use field-specific generation logic based on field type and name
            value = self._generate_field_value(object_name, field, pattern)
            
            if value is not None:
                record[field_name] = value
        
        # Second pass: Handle any required fields that weren't set
        for field_name in metadata.get('required_fields', []):
            if field_name not in record and field_name in fields:
                value = self._generate_required_field_value(object_name, fields[field_name])
                if value is not None:
                    record[field_name] = value
        
        # Return the generated record
        return record
    
    def _generate_field_value(self, object_name, field, pattern=None):
        """
        Generate a value for a specific field
        
        Args:
            object_name (str): API name of the Salesforce object
            field (dict): Field metadata
            pattern (dict): Optional patterns to follow for generation
            
        Returns:
            Various: Generated value appropriate for the field
        """
        field_name = field.get('name', '')
        field_type = field.get('type', '').lower()
        field_label = field.get('label', '').lower()
        
        # Check for field in patterns
        if pattern and field_name in pattern.get('field_distributions', {}):
            # Use value distribution from patterns when possible
            dist = pattern['field_distributions'][field_name]
            values = list(dist.keys())
            weights = list(dist.values())
            
            # Return a value based on observed distribution
            if values:
                return random.choices(values, weights=weights)[0]
        
        # Use field-specific generation based on type
        try:
            # Text fields
            if field_type in ('string', 'textarea'):
                return self._generate_string_value(object_name, field, pattern)
                
            # Selection fields
            elif field_type == 'picklist':
                return self._generate_picklist_value(field)
                
            elif field_type == 'multipicklist':
                return self._generate_multipicklist_value(field)
                
            # Boolean fields
            elif field_type == 'boolean':
                # Check context of field
                lower_name = field_name.lower()
                positive_terms = ['active', 'enabled', 'current', 'approved', 'verified']
                negative_terms = ['inactive', 'disabled', 'canceled', 'rejected', 'deleted']
                
                if any(term in lower_name for term in positive_terms):
                    return random.choices([True, False], weights=[0.7, 0.3])[0]
                elif any(term in lower_name for term in negative_terms):
                    return random.choices([True, False], weights=[0.3, 0.7])[0]
                else:
                    return random.choice([True, False])
                    
            # Number fields with ranges based on field context
            elif field_type in ('double', 'percent', 'currency'):
                return self._generate_numeric_value(field_name, field_type, field)
                
            # Integer fields
            elif field_type == 'int':
                return self._generate_integer_value(field_name, field)
                
            # Reference fields using valid IDs
            elif field_type == 'reference':
                return self._generate_reference_value(field)
                
            # Date fields
            elif field_type == 'date':
                return self._generate_date_value(field_name)
                
            # Datetime fields
            elif field_type == 'datetime':
                return self._generate_datetime_value(field_name)
                
            # Email fields
            elif field_type == 'email':
                return fake.email()
                
            # Phone fields
            elif field_type == 'phone':
                return fake.phone_number()
                
            # URL fields
            elif field_type == 'url':
                return fake.url()
                
            # Default: return None for unsupported field types
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error generating value for field {field_name}: {e}")
            return None
    
    def _generate_required_field_value(self, object_name, field):
        """
        Generate a value for a required field, with extra care to ensure validity
        
        Args:
            object_name (str): API name of the Salesforce object
            field (dict): Field metadata
            
        Returns:
            Various: Generated value appropriate for the field
        """
        field_name = field.get('name', '')
        field_type = field.get('type', '').lower()
        
        # For required fields, first try to get valid values from Salesforce
        field_key = f"{object_name}.{field_name}"
        
        # Fetch field values if we haven't already
        if field_key not in self.cache['field_values']:
            self._fetch_field_values(object_name, field_name)
            
        # If we have cached values, use one of them
        if field_key in self.cache['field_values'] and self.cache['field_values'][field_key]:
            return random.choice(self.cache['field_values'][field_key])
            
        # Otherwise use standard generation logic with validation
        value = self._generate_field_value(object_name, field)
        
        # Ensure string fields meet minimum length requirements
        if field_type in ('string', 'textarea') and value is not None and field.get('length'):
            min_length = 1  # Minimum for required fields
            if len(value) < min_length:
                # Pad to minimum length
                value = value + ' ' + fake.word() * (min_length - len(value))
                
        return value
    
    def _generate_string_value(self, object_name, field, pattern=None):
        """
        Generate a value for a string field based on its context
        
        Args:
            object_name (str): API name of the Salesforce object
            field (dict): Field metadata
            pattern (dict): Optional patterns to follow for generation
            
        Returns:
            str: Generated string value
        """
        field_name = field.get('name', '').lower()
        field_label = field.get('label', '').lower()
        max_length = field.get('length', 255)
        
        # Check if we have format patterns for this field
        if pattern and field_name in pattern.get('field_formats', {}):
            format_info = pattern['field_formats'][field_name]
            format_type = format_info.get('type')
            
            if format_type == 'email':
                return fake.email()
                
            elif format_type == 'phone':
                return fake.phone_number()
                
            elif format_type == 'numeric':
                # Generate a string of digits with observed length
                lengths = format_info.get('lengths', [max_length])
                length = random.choice(lengths)
                return ''.join(random.choices('0123456789', k=length))
                
            elif format_type == 'date':
                date_format = format_info.get('format', 'yyyy-mm-dd')
                date = fake.date_this_decade()
                
                if date_format == 'yyyy-mm-dd':
                    return date.strftime('%Y-%m-%d')
                elif date_format == 'mm/dd/yyyy':
                    return date.strftime('%m/%d/%Y')
                elif date_format == 'mm-dd-yyyy':
                    return date.strftime('%m-%d-%Y')
                else:
                    return date.strftime('%Y-%m-%d')
        
        # Handle standard field name patterns
        # Email fields
        if 'email' in field_name or 'email' in field_label:
            return fake.email()
            
        # Name fields
        elif field_name == 'name' or field_label == 'name':
            if object_name.lower() in ('account', 'accountinfo'):
                return fake.company()[:max_length]
            elif object_name.lower() in ('contact', 'lead', 'user'):
                return fake.name()[:max_length]
            else:
                # Try to intelligently name based on object
                if 'product' in object_name.lower():
                    return fake.bs()[:max_length]
                elif 'opportunity' in object_name.lower():
                    # Opportunity names often include customer name and project type
                    return f"{fake.company()} - {fake.catch_phrase().split()[0]}"[:max_length]
                else:
                    return fake.bs()[:max_length]
                    
        # First/last name fields
        elif 'first' in field_name or 'firstname' in field_name:
            return fake.first_name()
        elif 'last' in field_name or 'lastname' in field_name:
            return fake.last_name()
            
        # Middle name/initial
        elif 'middle' in field_name:
            if max_length <= 2:
                return fake.random_letter().upper() + "."
            else:
                return fake.first_name()
                
        # Address fields
        elif 'street' in field_name or 'address' in field_name and 'line' in field_name:
            return fake.street_address()
        elif 'city' in field_name:
            return fake.city()
        elif 'state' in field_name or 'province' in field_name:
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
            
        # Default case - generate a word or short phrase
        else:
            if max_length < 10:
                return fake.word()[:max_length]
            else:
                return fake.catch_phrase()[:max_length]
    
    def _generate_picklist_value(self, field):
        """
        Generate a value for a picklist field
        
        Args:
            field (dict): Field metadata
            
        Returns:
            str: Valid picklist value
        """
        picklist_values = field.get('picklistValues', [])
        
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
    
    def _generate_multipicklist_value(self, field):
        """
        Generate a value for a multi-select picklist field
        
        Args:
            field (dict): Field metadata
            
        Returns:
            str: Semicolon-delimited list of picklist values
        """
        picklist_values = field.get('picklistValues', [])
        
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
    
    def _generate_numeric_value(self, field_name, field_type, field):
        """
        Generate a numeric value appropriate for the field context
        
        Args:
            field_name (str): API name of the field
            field_type (str): Type of the field
            field (dict): Field metadata
            
        Returns:
            float: Generated numeric value
        """
        precision = field.get('precision', 18)
        scale = field.get('scale', 2)
        
        # Default ranges
        min_val = 0
        max_val = 100
        
        # Adjust ranges based on field context
        lower_name = field_name.lower()
        
        # Special handling for geolocation fields
        if 'latitude' in lower_name:
            # Latitude must be between -90 and +90
            return round(random.uniform(-90, 90), 6)
        elif 'longitude' in lower_name:
            # Longitude must be between -180 and +180
            return round(random.uniform(-180, 180), 6)
            
        # Handle amounts, prices, costs
        elif any(term in lower_name for term in ['amount', 'price', 'cost', 'revenue']):
            min_val = 10
            max_val = 10000
            
        # Handle percentages
        elif 'percent' in lower_name or field_type == 'percent':
            min_val = 0
            max_val = 100
            
        # Handle quantities
        elif any(term in lower_name for term in ['quantity', 'count', 'number']):
            min_val = 1
            max_val = 50
            
        # Handle rates and multipliers
        elif any(term in lower_name for term in ['rate', 'multiplier', 'factor']):
            min_val = 0.1
            max_val = 5
            
        # Generate a value within the appropriate range with proper scale
        value = round(random.uniform(min_val, max_val), scale)
        
        return value
    
    def _generate_integer_value(self, field_name, field):
        """
        Generate an integer value appropriate for the field context
        
        Args:
            field_name (str): API name of the field
            field (dict): Field metadata
            
        Returns:
            int: Generated integer value
        """
        lower_name = field_name.lower()
        
        # Default ranges
        min_val = 0
        max_val = 100
        
        # Adjust ranges based on field context
        if any(term in lower_name for term in ['quantity', 'count', 'number']):
            min_val = 1
            max_val = 50
            
        elif 'age' in lower_name:
            min_val = 18
            max_val = 80
            
        elif 'year' in lower_name:
            current_year = datetime.now().year
            min_val = current_year - 5
            max_val = current_year + 5
            
        elif 'day' in lower_name:
            min_val = 1
            max_val = 30
            
        elif 'month' in lower_name:
            min_val = 1
            max_val = 12
            
        # Generate a value within the appropriate range
        return random.randint(min_val, max_val)
    
    def _generate_reference_value(self, field):
        """
        Generate a reference value (ID) for a lookup field
        
        Args:
            field (dict): Field metadata
            
        Returns:
            str: Valid Salesforce ID or None
        """
        # Skip specific fields that should be null
        field_name_lower = field.get('name', '').lower()
        if 'dandbcompanyid' in field_name_lower:
            return None
            
        # Get reference targets
        reference_to = field.get('referenceTo', [])
        if not reference_to or not isinstance(reference_to, list):
            return None
            
        # Get the first reference target
        ref_object = reference_to[0]
        
        # Check if we have cached IDs for this object
        if ref_object not in self.cache['record_ids']:
            self._fetch_record_ids(ref_object)
            
        # Use a cached ID if available
        if ref_object in self.cache['record_ids'] and self.cache['record_ids'][ref_object]:
            return random.choice(self.cache['record_ids'][ref_object])
            
        # Fall back to placeholder IDs if no cached IDs available
        id_map = {
            'Account': '001000000000001AAA',
            'Contact': '003000000000001AAA',
            'Opportunity': '006000000000001AAA',
            'Lead': '00Q000000000001AAA',
            'Case': '500000000000001AAA',
            'User': '005000000000001AAA'
        }
        
        return id_map.get(ref_object)
    
    def _generate_date_value(self, field_name):
        """
        Generate a date value appropriate for the field context
        
        Args:
            field_name (str): API name of the field
            
        Returns:
            str: ISO format date string
        """
        lower_name = field_name.lower()
        
        # Birth dates
        if any(term in lower_name for term in ['birth', 'dob']):
            return fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat()
            
        # Expiration dates
        elif any(term in lower_name for term in ['expiry', 'expiration', 'end']):
            return fake.date_between(start_date='today', end_date='+3y').isoformat()
            
        # Start dates
        elif any(term in lower_name for term in ['start', 'begin', 'commencement']):
            return fake.date_between(start_date='-30d', end_date='+90d').isoformat()
            
        # Due dates
        elif 'due' in lower_name:
            return fake.date_between(start_date='today', end_date='+60d').isoformat()
            
        # Creation dates
        elif 'created' in lower_name or 'registered' in lower_name:
            return fake.date_between(start_date='-2y', end_date='today').isoformat()
            
        # Close dates for opportunities
        elif 'close' in lower_name:
            # Typically in the near future
            return fake.date_between(start_date='today', end_date='+180d').isoformat()
            
        # Default date range
        else:
            return fake.date_between(start_date='-1y', end_date='+1y').isoformat()
    
    def _generate_datetime_value(self, field_name):
        """
        Generate a datetime value appropriate for the field context
        
        Args:
            field_name (str): API name of the field
            
        Returns:
            str: ISO format datetime string
        """
        lower_name = field_name.lower()
        
        # Creation dates
        if any(term in lower_name for term in ['created', 'registered']):
            return fake.date_time_between(start_date='-1y', end_date='now').isoformat()
            
        # Modification dates
        elif any(term in lower_name for term in ['modified', 'updated', 'last']):
            return fake.date_time_between(start_date='-3m', end_date='now').isoformat()
            
        # Scheduled events
        elif any(term in lower_name for term in ['scheduled', 'appointment', 'meeting']):
            # Generate during business hours
            future_date = fake.date_time_between(start_date='+1d', end_date='+60d')
            business_hour = random.randint(9, 17)  # 9am to 5pm
            future_date = future_date.replace(hour=business_hour, minute=random.choice([0, 15, 30, 45]))
            return future_date.isoformat()
            
        # Default datetime range
        else:
            return fake.date_time_between(start_date='-1y', end_date='+1y').isoformat()
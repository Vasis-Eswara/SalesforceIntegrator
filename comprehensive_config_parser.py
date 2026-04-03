"""
Comprehensive Salesforce configuration parser
Handles ALL possible field creation patterns and formats
"""
import re
import logging
from faker_utils import fake

logger = logging.getLogger(__name__)


def analyze_prompt_for_configuration(prompt, existing_objects=None):
    """
    Comprehensive natural language prompt analyzer for Salesforce configuration
    Handles all common field creation patterns and formats
    """
    if existing_objects is None:
        existing_objects = []
    
    actions = []
    seen_objects = set()
    
    try:
        prompt_lower = prompt.lower()
        logger.info(f"Analyzing prompt: '{prompt}'")
        
        # PHASE 1: Multi-field list parsing (highest priority)
        if _parse_field_list(prompt_lower, actions):
            logger.info(f"Field list parsed successfully, {len(actions)} actions generated")
        
        # PHASE 2: Single field patterns
        elif _parse_single_field(prompt_lower, actions):
            logger.info(f"Single field parsed successfully, {len(actions)} actions generated")
        
        # PHASE 3: Object creation patterns
        elif _parse_object_creation(prompt_lower, actions, seen_objects):
            logger.info(f"Object creation parsed successfully")
        
        # PHASE 4: Complex patterns (object + field combinations)
        elif _parse_complex_patterns(prompt_lower, actions, seen_objects):
            logger.info(f"Complex pattern parsed successfully")
        
        # PHASE 5: Validation rules
        elif _parse_validation_rules(prompt_lower, actions, existing_objects):
            logger.info(f"Validation rule parsed successfully")
        
        return {
            "type": "configuration",
            "actions": actions,
            "analysis_method": "rule_based_with_faker",
            "prompt_analyzed": prompt
        }
        
    except Exception as e:
        logger.error(f"Error analyzing prompt: {str(e)}")
        return {"error": f"Error analyzing prompt: {str(e)}"}


def _parse_field_list(prompt_lower, actions):
    """
    Parse field lists in ALL possible formats:
    - "create the following fields under object X: 1. name -- type 2. field -- type"
    - "add these fields to object X: field1 (type), field2 (type)"
    - "object X needs: field1 - type, field2 - type"
    - "for object X create: field1: type, field2: type"
    """
    
    # Pattern 1: "create/add fields under/to object X: list"
    list_patterns = [
        # Standard colon-separated formats
        r'(?:create|add|make)\s+(?:the\s+)?(?:following\s+)?fields?\s+(?:under|to|on|in|for)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?([a-zA-Z_][a-zA-Z0-9_\s]*)\s*:\s*(.*)',
        r'(?:add|create|make)\s+(?:these\s+)?(?:the\s+)?(?:following\s+)?fields?\s+(?:to|under|on|in|for)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?([a-zA-Z_][a-zA-Z0-9_\s]*)\s*:\s*(.*)',
        r'(?:object\s+)?([a-zA-Z_][a-zA-Z0-9_\s]*)\s+(?:needs|requires)\s*:\s*(.*)',
        r'(?:create|make)\s+fields?\s+(?:for|on)\s+(?:the\s+)?(?:object\s+)?([a-zA-Z_][a-zA-Z0-9_\s]*)\s*:\s*(.*)',
        r'(?:under|on|in)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?([a-zA-Z_][a-zA-Z0-9_\s]*)\s*:?\s+(?:create|add)\s+(?:the\s+)?(?:following\s+)?fields?\s*:?\s*(.*)',
        # NEW: Handle comma-separated lists without colon - "create fields A, B, C under object X"
        r'(?:create|add|make)\s+(?:the\s+)?(?:following\s+)?fields?\s+([a-zA-Z0-9_,\s]+?)\s+(?:under|to|on|in|for)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?([a-zA-Z_][a-zA-Z0-9_\s]*)',
        # NEW: Handle "under object X create fields A, B, C" 
        r'(?:under|on|in)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?([a-zA-Z_][a-zA-Z0-9_\s]*)\s+(?:create|add|make)\s+(?:the\s+)?(?:following\s+)?fields?\s+([a-zA-Z0-9_,\s]+)'
    ]
    
    for i, pattern in enumerate(list_patterns):
        match = re.search(pattern, prompt_lower, re.DOTALL)
        if match:
            logger.info(f"Multi-field pattern {i+1} matched: {pattern}")
            
            # Handle different group arrangements based on pattern
            if i < 5:  # Traditional patterns: object first, then fields
                object_name = match.group(1).strip().replace(' ', '_')
                field_list_text = match.group(2).strip()
            else:  # New patterns: fields first, then object
                if i == 5:  # "create fields A, B, C under object X"
                    field_list_text = match.group(1).strip()
                    object_name = match.group(2).strip().replace(' ', '_')
                else:  # "under object X create fields A, B, C"
                    object_name = match.group(1).strip().replace(' ', '_')
                    field_list_text = match.group(2).strip()
            
            logger.info(f"Extracted object: {object_name}, fields: {field_list_text}")
            
            # Clean up target object name
            object_name = _normalize_object_name(object_name)
            
            # Parse the field list
            parsed_fields = _parse_field_list_content(field_list_text)
            
            if parsed_fields:  # Only proceed if we found fields
                for field_info in parsed_fields:
                    field_name = field_info['name']
                    field_type = field_info['type']
                    
                    # Clean up field name
                    if not field_name.endswith('__c'):
                        field_name += '__c'
                    
                    # Generate field details
                    field_details = _generate_field_details(field_name, field_type)
                    
                    actions.append({
                        "type": "create_field",
                        "target": {"object": object_name, "field": field_name},
                        "details": field_details
                    })
                
                logger.info(f"Successfully parsed {len(parsed_fields)} fields for {object_name}")
                return True
    
    return False


def _parse_field_list_content(field_list_text):
    """
    Parse various field list formats with comprehensive pattern matching
    """
    fields = []
    
    # Remove common separators and normalize
    field_list_text = re.sub(r'\s+', ' ', field_list_text)
    
    # Pattern 1: Numbered list with -- or - separator
    # "1. tendulkar -- text 2. tampering -- number"
    numbered_pattern = r'(?:\d+\.?\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:--|-{1,2})\s*([a-zA-Z_][a-zA-Z0-9_]*)'
    numbered_matches = re.findall(numbered_pattern, field_list_text, re.IGNORECASE)
    
    if numbered_matches:
        for field_name, field_type in numbered_matches:
            fields.append({
                'name': field_name.strip(),
                'type': _normalize_field_type(field_type.strip())
            })
        return fields
    
    # Pattern 2: Parentheses format
    # "name (type), field (type)" or "1. name (type) 2. field (type)"
    paren_pattern = r'(?:\d+\.?\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)'
    paren_matches = re.findall(paren_pattern, field_list_text, re.IGNORECASE)
    
    if paren_matches:
        for field_name, field_type in paren_matches:
            fields.append({
                'name': field_name.strip(),
                'type': _normalize_field_type(field_type.strip())
            })
        return fields
    
    # Pattern 3: Colon separator
    # "name: type, field: type"
    colon_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*)'
    colon_matches = re.findall(colon_pattern, field_list_text, re.IGNORECASE)
    
    if colon_matches:
        for field_name, field_type in colon_matches:
            fields.append({
                'name': field_name.strip(),
                'type': _normalize_field_type(field_type.strip())
            })
        return fields
    
    # Pattern 4: Simple comma-separated with types
    # "name - type, field - type"
    dash_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*-\s*([a-zA-Z_][a-zA-Z0-9_]*)'
    dash_matches = re.findall(dash_pattern, field_list_text, re.IGNORECASE)
    
    if dash_matches:
        for field_name, field_type in dash_matches:
            fields.append({
                'name': field_name.strip(),
                'type': _normalize_field_type(field_type.strip())
            })
        return fields
    
    # Pattern 5: Simple comma-separated field names WITHOUT types
    # "phonenumber, pincode, SSN, date of birth" - infer types from names
    if ',' in field_list_text:
        field_names = [name.strip() for name in field_list_text.split(',')]
        field_names = [name for name in field_names if name and re.match(r'^[a-zA-Z_][a-zA-Z0-9_\s]*$', name)]
        
        if field_names:
            logger.info(f"Found comma-separated fields: {field_names}")
            for field_name in field_names:
                # Clean up field name (replace spaces with underscores)
                clean_name = field_name.replace(' ', '_')
                # Infer type from field name
                field_type = _infer_field_type(clean_name)
                fields.append({
                    'name': clean_name,
                    'type': field_type
                })
            return fields
    
    # Pattern 6: Single field name (fallback)
    # Just "fieldname" - infer type from name
    single_field_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_\s]*)$', field_list_text.strip())
    if single_field_match:
        field_name = single_field_match.group(1).strip().replace(' ', '_')
        field_type = _infer_field_type(field_name)
        fields.append({
            'name': field_name,
            'type': field_type
        })
        return fields
    
    return fields


def _normalize_field_type(field_type):
    """
    Normalize field type variations to standard Salesforce types
    """
    type_mapping = {
        'text': 'text',
        'string': 'text',
        'number': 'number',
        'numeric': 'number',
        'integer': 'number',
        'int': 'number',
        'longtext': 'textarea',
        'long text': 'textarea',
        'textarea': 'textarea',
        'email': 'email',
        'phone': 'phone',
        'date': 'date',
        'datetime': 'datetime',
        'timestamp': 'datetime',
        'boolean': 'checkbox',
        'checkbox': 'checkbox',
        'currency': 'currency',
        'percent': 'percent',
        'url': 'url',
        'picklist': 'picklist'
    }
    
    return type_mapping.get(field_type.lower(), 'text')


def _normalize_object_name(object_name):
    """
    Normalize object names handling standard vs custom objects
    """
    standard_objects = ['contact', 'account', 'lead', 'opportunity', 'case', 'user', 'campaign', 'task', 'event', 'activity']
    if object_name.lower() in standard_objects:
        return object_name.capitalize()
    elif not object_name.endswith('__c'):
        return object_name + '__c'
    return object_name


def _parse_single_field(prompt_lower, actions):
    """
    Parse single field creation patterns
    """
    field_patterns = [
        # Pattern: create/add field named "name" under/on object "object" (handles quotes and no quotes)
        (r'(?:create|add)\s+(?:a\s+)?field\s+(?:called|named)\s+["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?\s+(?:under|on|to|in)\s+(?:the\s+)?(?:object\s+)?["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?', 'named_field_to_object'),
        # Pattern: add [field_name] field to [object_name]
        (r'add\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+field\s+to\s+([a-zA-Z_][a-zA-Z0-9_\s]*)', 'field_to_object'),
        # Pattern: create [field_name] field for [object_name]
        (r'create\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+field\s+for\s+([a-zA-Z_][a-zA-Z0-9_\s]*)', 'field_for_object'),
        # Pattern: add [type] field [field_name] to [object_name]
        (r'add\s+(text|number|email|phone|date|datetime|checkbox|picklist|currency|percent|url)\s+field\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+to\s+([a-zA-Z_][a-zA-Z0-9_\s]*)', 'type_field_to_object'),
        # Pattern: [object_name] with [field_name] field
        (r'([a-zA-Z_][a-zA-Z0-9_\s]*)\s+with\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+field', 'object_with_field')
    ]
    
    for pattern, pattern_type in field_patterns:
        matches = re.finditer(pattern, prompt_lower)
        for match in matches:
            if pattern_type == 'named_field_to_object':
                field_name = match.group(1).strip().replace(' ', '_')
                target_object = match.group(2).strip().replace(' ', '_')
                field_type = _infer_field_type(field_name)
            elif pattern_type == 'field_to_object':
                field_name = match.group(1).strip().replace(' ', '_')
                target_object = match.group(2).strip().replace(' ', '_')
                field_type = _infer_field_type(field_name)
            elif pattern_type == 'field_for_object':
                field_name = match.group(1).strip().replace(' ', '_')
                target_object = match.group(2).strip().replace(' ', '_')
                field_type = _infer_field_type(field_name)
            elif pattern_type == 'type_field_to_object':
                field_type = match.group(1).strip()
                field_name = match.group(2).strip().replace(' ', '_')
                target_object = match.group(3).strip().replace(' ', '_')
            elif pattern_type == 'object_with_field':
                target_object = match.group(1).strip().replace(' ', '_')
                field_name = match.group(2).strip().replace(' ', '_')
                field_type = _infer_field_type(field_name)
            
            # Clean up field name
            if not field_name.endswith('__c'):
                field_name += '__c'
            
            # Normalize target object
            target_object = _normalize_object_name(target_object)
            
            # Generate realistic field configuration based on type
            field_details = _generate_field_details(field_name, field_type)
            
            actions.append({
                "type": "create_field",
                "target": {"object": target_object, "field": field_name},
                "details": field_details
            })
            
            logger.info(f"Successfully created field action: {field_name} on {target_object}")
            return True
    
    logger.info("No single field patterns matched")
    return False


def _parse_object_creation(prompt_lower, actions, seen_objects):
    """
    Parse object creation patterns - Enhanced for multiple objects
    """
    # Enhanced patterns for multiple object creation
    object_patterns = [
        # Multiple objects patterns - key addition for your use case
        r'create.*?(?:custom\s+)?objects?\s+called\s+([^.!?]+)',
        r'create.*?(?:custom\s+)?objects?\s+named\s+([^.!?]+)', 
        r'create.*?(?:custom\s+)?objects?\s+for\s+([^.!?]+)',
        r'(?:make|build).*?(?:custom\s+)?objects?\s+called\s+([^.!?]+)',
        r'add.*?(?:custom\s+)?objects?\s+called\s+([^.!?]+)',
        
        # Single object patterns (fallback)
        r'create.*(?:object|custom object).*(?:called|named)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
        r'(?:create|add|make)\s+(?:an?|the)?\s*object\s+(?:called|named)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
        r'(?:object|custom object)\s+(?:called|named)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
        r'new\s+(?:object|custom object)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1'
    ]
    
    found_objects = False
    
    # First try multiple object patterns
    for i, pattern in enumerate(object_patterns[:5]):  # First 5 are multiple object patterns
        match = re.search(pattern, prompt_lower)
        if match:
            objects_text = match.group(1).strip()
            logger.info(f"Found multiple objects text: '{objects_text}'")
            
            # Parse multiple object names with enhanced splitting
            object_names = _parse_multiple_object_names(objects_text)
            logger.info(f"Parsed object names: {object_names}")
            
            for obj_name in object_names:
                obj_name = obj_name.strip().strip('"\'.,')
                if obj_name and obj_name.lower() not in seen_objects:
                    object_name = obj_name
                    if not object_name.endswith('__c'):
                        object_name += '__c'
                    
                    seen_objects.add(obj_name.lower())
                    
                    actions.append({
                        "type": "create_object",
                        "target": {"object": object_name},
                        "details": {
                            "api_name": object_name,
                            "label": _create_label_from_name(obj_name),
                            "plural_label": _create_label_from_name(obj_name) + 's',
                            "description": f"Custom object for {obj_name.lower()} management",
                            "deployment_status": "Deployed",
                            "sharing_model": "ReadWrite"
                        }
                    })
                    found_objects = True
                    logger.info(f"Added object action for '{obj_name}' -> '{object_name}'")
            
            if found_objects:
                return found_objects
    
    # If no multiple objects found, try single object patterns
    for pattern in object_patterns[5:]:  # Single object patterns
        matches = re.finditer(pattern, prompt_lower)
        for match in matches:
            if len(match.groups()) >= 2:
                object_name = match.group(2).strip()
            else:
                object_name = match.group(1).strip()
            
            # Clean up object name
            if not object_name.endswith('__c'):
                object_name += '__c'
            
            # Skip if we've already processed this object
            if object_name in seen_objects:
                continue
            seen_objects.add(object_name)
            
            actions.append({
                "type": "create_object",
                "target": {"object": object_name},
                "details": {
                    "api_name": object_name,
                    "label": object_name.replace('__c', '').replace('_', ' ').title(),
                    "plural_label": object_name.replace('__c', '').replace('_', ' ').title() + 's',
                    "description": f"Custom object for {object_name.replace('__c', '').replace('_', ' ').lower()} management",
                    "deployment_status": "Deployed",
                    "sharing_model": "ReadWrite"
                }
            })
            found_objects = True
    
    return found_objects


def _parse_complex_patterns(prompt_lower, actions, seen_objects):
    """
    Parse complex object + field combinations.
    Handles patterns like:
      "Create a Project object with fields Name, Status, and Budget"
      "Create Invoice object with field Amount"
    """
    # ------------------------------------------------------------------ #
    # Pattern A: "create [a] <name> object with fields <list>"  (plural)  #
    # ------------------------------------------------------------------ #
    multi_field_pattern = re.search(
        r'(?:create|make|build)\s+(?:an?\s+)?([a-zA-Z][a-zA-Z0-9_\s]*?)\s+object\s+with\s+fields?\s+(.+)',
        prompt_lower
    )
    if multi_field_pattern:
        object_raw = multi_field_pattern.group(1).strip()
        field_list_text = multi_field_pattern.group(2).strip()

        object_name = object_raw.replace(' ', '_')
        if not object_name.endswith('__c'):
            object_name += '__c'

        if object_name not in seen_objects:
            seen_objects.add(object_name)
            label = object_raw.title()
            actions.append({
                "type": "create_object",
                "target": {"object": object_name},
                "details": {
                    "api_name": object_name,
                    "label": label,
                    "plural_label": label + 's',
                    "description": f"Custom object for {object_raw.lower()} management",
                    "deployment_status": "Deployed",
                    "sharing_model": "ReadWrite",
                }
            })

            # Parse the field list (comma/and separated)
            raw_names = re.split(r',\s*|\s+and\s+', field_list_text)
            for raw in raw_names:
                fname = raw.strip()
                fname = re.sub(r'^(?:and|or)\s+', '', fname, flags=re.IGNORECASE).strip()
                fname = fname.replace(' ', '_')
                if not fname or fname in ('', 'and', 'or', 'the', 'a', 'an'):
                    continue
                is_std_name = fname.lower() == 'name'
                api_field = fname if is_std_name else (fname if fname.endswith('__c') else fname + '__c')
                ftype = _infer_field_type(fname)
                fdetails = _generate_field_details(api_field, ftype)
                actions.append({
                    "type": "create_field",
                    "target": {"object": object_name, "field": api_field},
                    "details": fdetails,
                })
        return True

    # ------------------------------------------------------------------ #
    # Pattern B: standalone "create [a] <name> object" (no fields)        #
    # ------------------------------------------------------------------ #
    solo_obj_pattern = re.search(
        r'(?:create|make|build)\s+(?:an?\s+)?([a-zA-Z][a-zA-Z0-9_\s]*?)\s+object(?:\s*$|\s*[.,!?])',
        prompt_lower
    )
    if solo_obj_pattern:
        object_raw = solo_obj_pattern.group(1).strip()
        object_name = object_raw.replace(' ', '_')
        if not object_name.endswith('__c'):
            object_name += '__c'
        if object_name not in seen_objects:
            seen_objects.add(object_name)
            label = object_raw.title()
            actions.append({
                "type": "create_object",
                "target": {"object": object_name},
                "details": {
                    "api_name": object_name,
                    "label": label,
                    "plural_label": label + 's',
                    "description": f"Custom object for {object_raw.lower()} management",
                    "deployment_status": "Deployed",
                    "sharing_model": "ReadWrite",
                }
            })
        return True

    # ------------------------------------------------------------------ #
    # Legacy single-field patterns                                         #
    # ------------------------------------------------------------------ #
    complex_patterns = [
        r'create\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+object\s+with\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+field',
        r'make\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+object\s+with\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+field'
    ]

    found_complex = False
    for pattern in complex_patterns:
        matches = re.finditer(pattern, prompt_lower)
        for match in matches:
            object_name = match.group(1).strip().replace(' ', '_')
            field_name = match.group(2).strip().replace(' ', '_')

            if not object_name.endswith('__c'):
                object_name += '__c'
            if not field_name.endswith('__c'):
                field_name += '__c'

            if object_name in seen_objects:
                continue
            seen_objects.add(object_name)

            actions.append({
                "type": "create_object",
                "target": {"object": object_name},
                "details": {
                    "api_name": object_name,
                    "label": object_name.replace('__c', '').replace('_', ' ').title(),
                    "plural_label": object_name.replace('__c', '').replace('_', ' ').title() + 's',
                    "description": f"Custom object for {object_name.replace('__c', '').replace('_', ' ').lower()} data management",
                    "deployment_status": "Deployed",
                    "sharing_model": "ReadWrite"
                }
            })

            # Add field creation
            field_type = _infer_field_type(field_name)
            field_details = _generate_field_details(field_name, field_type)
            
            actions.append({
                "type": "create_field",
                "target": {"object": object_name, "field": field_name},
                "details": field_details
            })
            found_complex = True
    
    return found_complex


def _parse_validation_rules(prompt_lower, actions, existing_objects):
    """
    Parse validation rule patterns
    """
    validation_patterns = [
        r'validation.*rule.*(["\']?)([a-zA-Z_][a-zA-Z0-9_\s]*)\1',
        r'validate.*(["\']?)([a-zA-Z_][a-zA-Z0-9_\s]*)\1',
        r'rule.*to.*(?:ensure|check|validate).*(["\']?)([a-zA-Z_][a-zA-Z0-9_\s]*)\1'
    ]
    
    found_rules = False
    for pattern in validation_patterns:
        matches = re.finditer(pattern, prompt_lower)
        for match in matches:
            rule_name = match.group(2).strip().replace(' ', '_')
            target_object = _extract_target_object(prompt_lower, existing_objects)
            
            actions.append({
                "type": "create_validation_rule",
                "target": {"object": target_object, "rule": rule_name},
                "details": {
                    "name": rule_name,
                    "description": f"Validation rule for {rule_name.replace('_', ' ').lower()}",
                    "error_condition": "/* Add your validation logic here */",
                    "error_message": f"Please ensure {rule_name.replace('_', ' ').lower()} requirements are met.",
                    "active": True
                }
            })
            found_rules = True
    
    return found_rules


def _infer_field_type(field_name):
    """
    Infer field type from field name
    """
    field_name_lower = field_name.lower()
    
    if any(keyword in field_name_lower for keyword in ['email', 'mail']):
        return 'email'
    elif any(keyword in field_name_lower for keyword in ['phone', 'mobile', 'tel', 'phonenumber', 'phone_number']):
        return 'phone'
    elif any(keyword in field_name_lower for keyword in ['date', 'created', 'modified', 'birth', 'dob', 'date_of_birth']):
        return 'date'
    elif any(keyword in field_name_lower for keyword in ['time', 'timestamp']):
        return 'datetime'
    elif any(keyword in field_name_lower for keyword in ['description', 'comment', 'note']):
        return 'textarea'
    elif any(keyword in field_name_lower for keyword in ['price', 'cost', 'amount', 'salary']):
        return 'currency'
    elif any(keyword in field_name_lower for keyword in ['percent', 'rate', '%']):
        return 'percent'
    elif any(keyword in field_name_lower for keyword in ['url', 'website', 'link']):
        return 'url'
    elif any(keyword in field_name_lower for keyword in ['active', 'enabled', 'flag', 'is_']):
        return 'checkbox'
    elif any(keyword in field_name_lower for keyword in ['count', 'number', 'quantity', 'id', 'pincode', 'pin_code', 'zipcode', 'zip_code']):
        return 'number'
    elif any(keyword in field_name_lower for keyword in ['ssn', 'social_security', 'tax_id', 'ein', 'passport']):
        return 'text'  # Use text for sensitive data that needs formatting
    else:
        return 'text'


def _generate_field_details(field_name, field_type):
    """
    Generate comprehensive field details based on type
    """
    label = field_name.replace('__c', '').replace('_', ' ').title()
    
    base_details = {
        "api_name": field_name,
        "label": label,
        "description": f"{label} field generated with intelligent configuration",
        "required": False,
        "unique": False,
        "type": field_type.title()
    }
    
    # Add type-specific properties
    if field_type == 'text':
        base_details.update({
            "length": 255,
            "default_value": ""
        })
    elif field_type == 'textarea':
        base_details.update({
            "length": 32768,
            "visible_lines": 3
        })
    elif field_type == 'number':
        base_details.update({
            "precision": 18,
            "scale": 0,
            "default_value": 0
        })
    elif field_type == 'currency':
        base_details.update({
            "precision": 18,
            "scale": 2,
            "default_value": 0.00
        })
    elif field_type == 'percent':
        base_details.update({
            "precision": 3,
            "scale": 2,
            "default_value": 0
        })
    elif field_type == 'checkbox':
        base_details.update({
            "default_value": False
        })
    elif field_type == 'email':
        base_details.update({
            "unique": False
        })
    elif field_type == 'phone':
        base_details.update({
            "unique": False
        })
    elif field_type == 'url':
        base_details.update({
            "length": 255
        })
    
    return base_details


def _extract_target_object(prompt_lower, existing_objects):
    """Extract the target object name from prompt context"""
    # Look for "on [object]" or "for [object]" patterns
    object_patterns = [
        r'(?:on|for|to)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'([a-zA-Z_][a-zA-Z0-9_]*)\s+object'
    ]
    
    for pattern in object_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            return match.group(1).strip() + '__c'
    
    # Default to first existing object or generic custom object
    if existing_objects:
        return existing_objects[0]
    
    return 'Custom_Object__c'


def _parse_multiple_object_names(objects_text):
    """
    Parse multiple object names from text like "Project, projections, prompting, proper"
    """
    # Handle comma-separated, "and" separated, or space-separated names
    objects_text = objects_text.replace(' and ', ', ').replace(', and ', ', ')
    
    # Split by commas first, then by spaces if no commas
    if ',' in objects_text:
        object_names = [name.strip() for name in objects_text.split(',') if name.strip()]
    else:
        # Split by spaces, but be careful with multi-word names
        potential_names = objects_text.split()
        object_names = []
        for name in potential_names:
            name = name.strip().strip(',')
            if name:
                object_names.append(name)
    
    return [name for name in object_names if name and len(name) > 1]


def _create_label_from_name(name):
    """
    Create a proper label from object name
    """
    return name.replace('_', ' ').title()
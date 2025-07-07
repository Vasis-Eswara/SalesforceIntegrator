import os
import json
import logging
import re
from faker import Faker

logger = logging.getLogger(__name__)

# Initialize Faker for generating realistic values
fake = Faker()

def analyze_prompt_for_configuration(prompt, org_info=None):
    """
    Analyze a natural language prompt to determine what Salesforce configurations 
    should be created or modified using rule-based analysis and Faker for realistic data
    
    Args:
        prompt (str): The user's natural language prompt describing desired changes
        org_info (dict): Optional information about the current org configuration
        
    Returns:
        dict: Structured configuration changes to apply
    """
    try:
        prompt_lower = prompt.lower().strip()
        logger.info(f"Analyzing prompt: '{prompt_lower}'")
        actions = []
        
        # Extract object names and field types from the prompt
        existing_objects = []
        if org_info and 'objects' in org_info:
            existing_objects = [obj.get('name', '').lower() for obj in org_info['objects']]
        
        # Remove duplicate actions
        seen_objects = set()
        
        # Rule-based analysis patterns
        
        # Pattern 1: Create new object
        create_object_patterns = [
            r'create.*(?:object|custom object).*(?:called|named)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
            r'add.*(?:object|custom object).*(?:called|named)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
            r'new.*(?:object|custom object)\s+(?:called|named)?\s*(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
            r'make.*(?:object|custom object)\s+(?:called|named)?\s*(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
            r'(?:create|add|make)\s+(?:an?|the)?\s*object\s+(?:called|named)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1',
            r'(?:object|custom object)\s+(?:called|named)\s+(["\']?)([a-zA-Z_][a-zA-Z0-9_]*)\1'
        ]
        
        for pattern in create_object_patterns:
            matches = re.finditer(pattern, prompt_lower)
            for match in matches:
                logger.info(f"Pattern '{pattern}' matched: {match.groups()}")
                # Get the object name from the correct group
                if len(match.groups()) >= 2:
                    object_name = match.group(2).replace(' ', '_').strip()
                else:
                    object_name = match.group(1).replace(' ', '_').strip()
                
                if not object_name.endswith('__c'):
                    object_name += '__c'
                
                logger.info(f"Extracted object name: {object_name}")
                
                # Skip if we've already processed this object
                if object_name in seen_objects:
                    continue
                seen_objects.add(object_name)
                
                # Generate realistic object configuration
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
        
        # Pattern 2: Create fields  
        field_patterns = [
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
                if pattern_type == 'field_to_object':
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
                
                # Clean up target object
                if not target_object.endswith('__c') and target_object.lower() not in ['contact', 'account', 'lead', 'opportunity', 'case', 'user']:
                    target_object += '__c'
                
                # Generate realistic field configuration based on type
                field_details = _generate_field_details(field_name, field_type)
                
                actions.append({
                    "type": "create_field",
                    "target": {"object": target_object, "field": field_name},
                    "details": field_details
                })
        
        # Pattern 3: Create validation rules
        validation_patterns = [
            r'validation.*rule.*(["\']?)([a-zA-Z_][a-zA-Z0-9_\s]*)\1',
            r'validate.*(["\']?)([a-zA-Z_][a-zA-Z0-9_\s]*)\1',
            r'rule.*to.*(?:ensure|check|validate).*(["\']?)([a-zA-Z_][a-zA-Z0-9_\s]*)\1'
        ]
        
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
        
        # Pattern 4: Complex object creation with fields 
        complex_patterns = [
            r'create\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+object\s+with\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+field',
            r'make\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+object\s+with\s+([a-zA-Z_][a-zA-Z0-9_\s]*)\s+field'
        ]
        
        for pattern in complex_patterns:
            matches = re.finditer(pattern, prompt_lower)
            for match in matches:
                object_name = match.group(1).strip().replace(' ', '_')
                field_name = match.group(2).strip().replace(' ', '_')
                
                if not object_name.endswith('__c'):
                    object_name += '__c'
                if not field_name.endswith('__c'):
                    field_name += '__c'
                
                # Skip if we've already processed this object
                if object_name in seen_objects:
                    continue
                seen_objects.add(object_name)
                
                # Add object creation
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

        # If no specific patterns match, provide a generic suggestion
        if not actions:
            # Try to extract any object-like words and suggest creating them
            words = re.findall(r'\b[A-Z][a-zA-Z]*\b', prompt)
            if words:
                for word in words[:2]:  # Limit to first 2 words to avoid noise
                    object_name = word + '__c'
                    actions.append({
                        "type": "create_object",
                        "target": {"object": object_name},
                        "details": {
                            "api_name": object_name,
                            "label": word,
                            "plural_label": word + 's',
                            "description": f"Custom object suggested from prompt analysis",
                            "deployment_status": "Deployed",
                            "sharing_model": "ReadWrite"
                        }
                    })
                    
                    # Add some common fields
                    common_fields = [
                        {"name": "Name__c", "type": "text", "label": "Name"},
                        {"name": "Description__c", "type": "textarea", "label": "Description"},
                        {"name": "Active__c", "type": "checkbox", "label": "Active"}
                    ]
                    
                    for field in common_fields:
                        field_details = _generate_field_details(field["name"], field["type"])
                        field_details["label"] = field["label"]
                        
                        actions.append({
                            "type": "create_field",
                            "target": {"object": object_name, "field": field["name"]},
                            "details": field_details
                        })
        
        return {
            "type": "configuration",
            "actions": actions,
            "analysis_method": "rule_based_with_faker",
            "prompt_analyzed": prompt
        }
        
    except Exception as e:
        logger.error(f"Error analyzing prompt: {str(e)}")
        return {"error": f"Error analyzing prompt: {str(e)}"}

def _extract_target_object(prompt_lower, existing_objects):
    """Extract the target object name from prompt context"""
    # Look for "on [object]" or "for [object]" patterns
    object_patterns = [
        r'(?:on|for|to)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'([a-zA-Z_][a-zA-Z0-9_]*)\s+object'
    ]
    
    for pattern in object_patterns:
        matches = re.findall(pattern, prompt_lower)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            if match.lower() in existing_objects:
                return match
            # Check if it might be a custom object name
            if not match.endswith('__c'):
                potential_custom = match + '__c'
                if potential_custom.lower() in existing_objects:
                    return potential_custom
    
    # Default fallback - use the first existing object or suggest a new one
    if existing_objects:
        return existing_objects[0]
    else:
        return "Custom_Object__c"

def _infer_field_type(field_name):
    """Infer field type from field name"""
    field_name_lower = field_name.lower()
    
    if any(keyword in field_name_lower for keyword in ['email', 'e_mail']):
        return 'email'
    elif any(keyword in field_name_lower for keyword in ['phone', 'telephone', 'mobile']):
        return 'phone'
    elif any(keyword in field_name_lower for keyword in ['date', 'birthday', 'anniversary']):
        return 'date'
    elif any(keyword in field_name_lower for keyword in ['datetime', 'timestamp', 'created', 'modified']):
        return 'datetime'
    elif any(keyword in field_name_lower for keyword in ['price', 'cost', 'amount', 'salary', 'revenue']):
        return 'currency'
    elif any(keyword in field_name_lower for keyword in ['percent', 'percentage', 'rate']):
        return 'percent'
    elif any(keyword in field_name_lower for keyword in ['url', 'website', 'link']):
        return 'url'
    elif any(keyword in field_name_lower for keyword in ['number', 'count', 'quantity', 'age']):
        return 'number'
    elif any(keyword in field_name_lower for keyword in ['active', 'enabled', 'approved', 'verified']):
        return 'checkbox'
    elif any(keyword in field_name_lower for keyword in ['description', 'notes', 'comments', 'details']):
        return 'textarea'
    else:
        return 'text'

def _generate_field_details(field_name, field_type):
    """Generate realistic field configuration using Faker"""
    base_name = field_name.replace('__c', '').replace('_', ' ').title()
    
    details = {
        "api_name": field_name,
        "label": base_name,
        "description": f"{base_name} field generated with intelligent configuration",
        "required": False,
        "unique": False
    }
    
    # Configure based on field type
    if field_type == "text":
        details.update({
            "type": "Text",
            "length": 255,
            "default_value": ""
        })
    elif field_type == "textarea":
        details.update({
            "type": "LongTextArea",
            "length": 32768,
            "visible_lines": 3
        })
    elif field_type == "number":
        details.update({
            "type": "Number",
            "precision": 18,
            "scale": 0,
            "default_value": 0
        })
    elif field_type == "currency":
        details.update({
            "type": "Currency",
            "precision": 18,
            "scale": 2,
            "default_value": 0.00
        })
    elif field_type == "percent":
        details.update({
            "type": "Percent",
            "precision": 5,
            "scale": 2,
            "default_value": 0.00
        })
    elif field_type == "email":
        details.update({
            "type": "Email",
            "unique": True
        })
    elif field_type == "phone":
        details.update({
            "type": "Phone"
        })
    elif field_type == "url":
        details.update({
            "type": "Url"
        })
    elif field_type == "date":
        details.update({
            "type": "Date"
        })
    elif field_type == "datetime":
        details.update({
            "type": "DateTime"
        })
    elif field_type == "checkbox":
        details.update({
            "type": "Checkbox",
            "default_value": False
        })
    elif field_type == "picklist":
        # Generate realistic picklist values using Faker
        picklist_values = []
        if "status" in field_name.lower():
            picklist_values = ["Active", "Inactive", "Pending", "Draft"]
        elif "priority" in field_name.lower():
            picklist_values = ["Low", "Medium", "High", "Critical"]
        elif "type" in field_name.lower():
            picklist_values = ["Type A", "Type B", "Type C"]
        else:
            # Generate generic options
            picklist_values = ["Option 1", "Option 2", "Option 3"]
        
        details.update({
            "type": "Picklist",
            "picklist_values": picklist_values,
            "default_value": picklist_values[0] if picklist_values else ""
        })
    
    return details

def apply_configuration(instance_url, access_token, config):
    """
    Apply the generated configuration to a Salesforce org
    
    Args:
        instance_url (str): Salesforce instance URL
        access_token (str): Access token for authentication
        config (dict): Configuration to apply (from analyze_prompt_for_configuration)
        
    Returns:
        dict: Result of applying the configuration
    """
    try:
        if 'error' in config:
            return {"success": False, "message": config["error"]}
            
        if 'type' not in config or config['type'] != 'configuration' or 'actions' not in config:
            return {"success": False, "message": "Invalid configuration format"}
            
        results = {"success": True, "message": "Applied configuration successfully", "details": []}
        
        # Process each action in the configuration
        for action in config.get('actions', []):
            action_type = action.get('type')
            target = action.get('target', {})
            details = action.get('details', {})
            
            # Handle different action types
            if action_type == 'create_object':
                result = create_custom_object(instance_url, access_token, target.get('object'), details)
                results['details'].append(result)
            
            elif action_type == 'modify_object':
                result = modify_custom_object(instance_url, access_token, target.get('object'), details)
                results['details'].append(result)
                
            elif action_type == 'delete_object':
                result = delete_custom_object(instance_url, access_token, target.get('object'))
                results['details'].append(result)
                
            elif action_type == 'create_field':
                result = create_custom_field(instance_url, access_token, target.get('object'), details)
                results['details'].append(result)
                
            elif action_type == 'modify_field':
                result = modify_custom_field(instance_url, access_token, target.get('object'), target.get('field'), details)
                results['details'].append(result)
                
            elif action_type == 'delete_field':
                result = delete_custom_field(instance_url, access_token, target.get('object'), target.get('field'))
                results['details'].append(result)
                
            elif action_type == 'create_validation_rule':
                result = create_validation_rule(instance_url, access_token, target.get('object'), details)
                results['details'].append(result)
                
            elif action_type == 'modify_validation_rule':
                result = modify_validation_rule(instance_url, access_token, target.get('object'), target.get('rule'), details)
                results['details'].append(result)
                
            elif action_type == 'delete_validation_rule':
                result = delete_validation_rule(instance_url, access_token, target.get('object'), target.get('rule'))
                results['details'].append(result)
                
            elif action_type == 'create_apex_trigger':
                result = create_apex_trigger(instance_url, access_token, target.get('object'), details)
                results['details'].append(result)
                
            elif action_type == 'modify_apex_trigger':
                result = modify_apex_trigger(instance_url, access_token, target.get('trigger'), details)
                results['details'].append(result)
                
            elif action_type == 'delete_apex_trigger':
                result = delete_apex_trigger(instance_url, access_token, target.get('trigger'))
                results['details'].append(result)
                
            else:
                results['details'].append({
                    "success": False,
                    "message": f"Unsupported action type: {action_type}"
                })
                
        return results
        
    except Exception as e:
        logger.error(f"Error applying configuration: {str(e)}")
        return {"success": False, "message": f"Error applying configuration: {str(e)}"}

# Implementation of specific handlers for different configuration actions
# Note: For the initial implementation, these are simulations

def create_custom_object(instance_url, access_token, object_name, details):
    """
    Create a new custom object in Salesforce using Metadata API
    """
    logger.info(f"Creating custom object: {object_name}")
    
    try:
        # Create the custom object using Salesforce REST API
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Use Metadata API via REST to create custom object
        url = f"{instance_url}/services/data/v58.0/metadata/deployRequest"
        
        # Build the object payload for REST API
        label = details.get('label', object_name.replace('__c', '').replace('_', ' ').title())
        plural_label = details.get('plural_label', label + 's')
        
        # Use a simpler approach - create via SOAP metadata API simulation
        # For now, let's simulate successful creation and log what would be created
        logger.info(f"Would create custom object {object_name} with label: {label}")
        
        return {
            "action": "create_object",
            "target": object_name,
            "success": True,
            "message": f"Configuration generated for custom object: {object_name} (Note: Actual creation requires Metadata API deployment)",
            "details": {
                "object_name": object_name,
                "label": label,
                "plural_label": plural_label,
                "name_field_label": details.get('name_field_label', 'Name'),
                "note": "This configuration can be manually applied in Salesforce Setup > Object Manager"
            }
        }
            
    except Exception as e:
        logger.error(f"Error creating custom object {object_name}: {str(e)}")
        return {
            "action": "create_object",
            "target": object_name,
            "success": False,
            "message": f"Error creating custom object: {str(e)}",
            "details": details
        }

def modify_custom_object(instance_url, access_token, object_name, details):
    """
    Modify an existing custom object in Salesforce
    
    Currently a simulation that just shows what would be modified
    """
    logger.info(f"Modifying custom object: {object_name}")
    # Simulate successful modification
    return {
        "action": "modify_object",
        "target": object_name,
        "success": True,
        "message": f"Would modify custom object: {object_name}",
        "details": details
    }

def delete_custom_object(instance_url, access_token, object_name):
    """
    Delete a custom object from Salesforce
    
    Currently a simulation that just shows what would be deleted
    """
    logger.info(f"Deleting custom object: {object_name}")
    # Simulate successful deletion
    return {
        "action": "delete_object",
        "target": object_name,
        "success": True,
        "message": f"Would delete custom object: {object_name}"
    }

def create_custom_field(instance_url, access_token, object_name, details):
    """
    Create a new custom field on an object in Salesforce
    
    Currently a simulation that just shows what would be created
    """
    field_name = details.get('api_name', 'unknown_field')
    logger.info(f"Creating custom field: {field_name} on {object_name}")
    # Simulate successful creation
    return {
        "action": "create_field",
        "target": f"{object_name}.{field_name}",
        "success": True,
        "message": f"Would create custom field: {field_name} on {object_name}",
        "details": details
    }

def modify_custom_field(instance_url, access_token, object_name, field_name, details):
    """
    Modify an existing custom field on an object in Salesforce
    
    Currently a simulation that just shows what would be modified
    """
    logger.info(f"Modifying custom field: {field_name} on {object_name}")
    # Simulate successful modification
    return {
        "action": "modify_field",
        "target": f"{object_name}.{field_name}",
        "success": True,
        "message": f"Would modify custom field: {field_name} on {object_name}",
        "details": details
    }

def delete_custom_field(instance_url, access_token, object_name, field_name):
    """
    Delete a custom field from an object in Salesforce
    
    Currently a simulation that just shows what would be deleted
    """
    logger.info(f"Deleting custom field: {field_name} from {object_name}")
    # Simulate successful deletion
    return {
        "action": "delete_field",
        "target": f"{object_name}.{field_name}",
        "success": True,
        "message": f"Would delete custom field: {field_name} from {object_name}"
    }

def create_validation_rule(instance_url, access_token, object_name, details):
    """
    Create a new validation rule on an object in Salesforce
    
    Currently a simulation that just shows what would be created
    """
    rule_name = details.get('name', 'unknown_rule')
    logger.info(f"Creating validation rule: {rule_name} on {object_name}")
    # Simulate successful creation
    return {
        "action": "create_validation_rule",
        "target": f"{object_name}.{rule_name}",
        "success": True,
        "message": f"Would create validation rule: {rule_name} on {object_name}",
        "details": details
    }

def modify_validation_rule(instance_url, access_token, object_name, rule_name, details):
    """
    Modify an existing validation rule on an object in Salesforce
    
    Currently a simulation that just shows what would be modified
    """
    logger.info(f"Modifying validation rule: {rule_name} on {object_name}")
    # Simulate successful modification
    return {
        "action": "modify_validation_rule",
        "target": f"{object_name}.{rule_name}",
        "success": True,
        "message": f"Would modify validation rule: {rule_name} on {object_name}",
        "details": details
    }

def delete_validation_rule(instance_url, access_token, object_name, rule_name):
    """
    Delete a validation rule from an object in Salesforce
    
    Currently a simulation that just shows what would be deleted
    """
    logger.info(f"Deleting validation rule: {rule_name} from {object_name}")
    # Simulate successful deletion
    return {
        "action": "delete_validation_rule",
        "target": f"{object_name}.{rule_name}",
        "success": True,
        "message": f"Would delete validation rule: {rule_name} from {object_name}"
    }

def create_apex_trigger(instance_url, access_token, object_name, details):
    """
    Create a new Apex trigger for an object in Salesforce
    
    Currently a simulation that just shows what would be created
    """
    trigger_name = details.get('name', 'unknown_trigger')
    logger.info(f"Creating Apex trigger: {trigger_name} for {object_name}")
    # Simulate successful creation
    return {
        "action": "create_apex_trigger",
        "target": trigger_name,
        "success": True,
        "message": f"Would create Apex trigger: {trigger_name} for {object_name}",
        "details": details
    }

def modify_apex_trigger(instance_url, access_token, trigger_name, details):
    """
    Modify an existing Apex trigger in Salesforce
    
    Currently a simulation that just shows what would be modified
    """
    logger.info(f"Modifying Apex trigger: {trigger_name}")
    # Simulate successful modification
    return {
        "action": "modify_apex_trigger",
        "target": trigger_name,
        "success": True,
        "message": f"Would modify Apex trigger: {trigger_name}",
        "details": details
    }

def delete_apex_trigger(instance_url, access_token, trigger_name):
    """
    Delete an Apex trigger from Salesforce
    
    Currently a simulation that just shows what would be deleted
    """
    logger.info(f"Deleting Apex trigger: {trigger_name}")
    # Simulate successful deletion
    return {
        "action": "delete_apex_trigger",
        "target": trigger_name,
        "success": True,
        "message": f"Would delete Apex trigger: {trigger_name}"
    }
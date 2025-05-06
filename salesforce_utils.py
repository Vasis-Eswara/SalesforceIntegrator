import os
import json
import logging
import requests
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Salesforce OAuth configuration
SF_CLIENT_ID = os.environ.get('SALESFORCE_CLIENT_ID', '')
SF_CLIENT_SECRET = os.environ.get('SALESFORCE_CLIENT_SECRET', '')

# Get the redirect URI from environment or use a default
SF_REDIRECT_URI = os.environ.get('SALESFORCE_REDIRECT_URI', 'https://2dbf6f12-560a-4cb9-8ca7-c2cd30a7fe4e-00-2kbskpp6fbk9s.worf.replit.dev/salesforce/callback')
logger.debug(f"Using redirect URI: '{SF_REDIRECT_URI}'")

# Make sure there's no trailing slash in the redirect URI
if SF_REDIRECT_URI.endswith('/'):
    SF_REDIRECT_URI = SF_REDIRECT_URI[:-1]


SF_LOGIN_URL = os.environ.get('SALESFORCE_LOGIN_URL', 'https://login.salesforce.com')

def get_auth_url():
    """Generate Salesforce OAuth authorization URL"""
    # Check if Salesforce credentials are configured
    if not SF_CLIENT_ID:
        raise Exception("Salesforce Client ID not configured. Please set the SALESFORCE_CLIENT_ID environment variable.")
        
    params = {
        'client_id': SF_CLIENT_ID,
        'redirect_uri': SF_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'api refresh_token offline_access'
    }
    auth_url = f"{SF_LOGIN_URL}/services/oauth2/authorize?{urlencode(params)}"
    logger.debug(f"Generated auth URL: {auth_url}")
    return auth_url

def get_access_token(code):
    """Exchange authorization code for access token"""
    # Check if Salesforce credentials are configured
    if not SF_CLIENT_ID or not SF_CLIENT_SECRET:
        raise Exception("Salesforce client credentials not configured. Please set the SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET environment variables.")
        
    token_url = f"{SF_LOGIN_URL}/services/oauth2/token"
    payload = {
        'grant_type': 'authorization_code',
        'client_id': SF_CLIENT_ID,
        'client_secret': SF_CLIENT_SECRET,
        'redirect_uri': SF_REDIRECT_URI,
        'code': code
    }
    
    response = None
    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting access token: {str(e)}")
        if response is not None:
            logger.error(f"Response: {response.text}")
        raise Exception(f"Failed to get access token: {str(e)}")

def refresh_access_token(refresh_token):
    """Refresh an expired access token"""
    token_url = f"{SF_LOGIN_URL}/services/oauth2/token"
    payload = {
        'grant_type': 'refresh_token',
        'client_id': SF_CLIENT_ID,
        'client_secret': SF_CLIENT_SECRET,
        'refresh_token': refresh_token
    }
    
    response = None
    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error refreshing token: {str(e)}")
        if response is not None:
            logger.error(f"Response: {response.text}")
        raise Exception(f"Failed to refresh token: {str(e)}")

def make_api_request(instance_url, access_token, endpoint, method='GET', data=None):
    """Make a request to Salesforce API with proper headers and error handling"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    url = f"{instance_url}{endpoint}"
    
    response = None
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PATCH':
            response = requests.patch(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request error ({method} {url}): {str(e)}")
        if response:
            logger.error(f"Response: {response.text}")
        if response and response.status_code == 401:
            raise Exception("Authentication error - token may have expired")
        raise Exception(f"API request failed: {str(e)}")

def get_salesforce_objects(instance_url, access_token):
    """Get list of objects from Salesforce"""
    endpoint = '/services/data/v58.0/sobjects/'
    response = make_api_request(instance_url, access_token, endpoint)
    
    # Filter objects to only include createable ones
    objects = []
    for obj in response.get('sobjects', []):
        if obj.get('createable') and not obj.get('deprecatedAndHidden'):
            objects.append({
                'name': obj.get('name'),
                'label': obj.get('label'),
                'custom': obj.get('custom', False)
            })
    
    # Sort objects by label
    objects.sort(key=lambda x: x['label'])
    return objects

def get_object_fields(instance_url, access_token, object_name):
    """Get fields for a specific Salesforce object"""
    endpoint = f'/services/data/v58.0/sobjects/{object_name}/describe/'
    response = make_api_request(instance_url, access_token, endpoint)
    
    fields = []
    for field in response.get('fields', []):
        # Skip system fields that shouldn't be populated manually
        if field.get('createable'):
            field_info = {
                'name': field.get('name'),
                'label': field.get('label'),
                'type': field.get('type'),
                'required': field.get('nillable') is False and not field.get('defaultedOnCreate'),
                'unique': field.get('unique', False),
                'custom': field.get('custom', False)
            }
            
            # Add reference information if it's a lookup/master-detail
            if field.get('type') in ('reference', 'lookup', 'masterdetail'):
                field_info['referenceTo'] = field.get('referenceTo', [])
                field_info['relationshipName'] = field.get('relationshipName')
            
            # Add picklist values if applicable
            if field.get('type') in ('picklist', 'multipicklist'):
                field_info['picklistValues'] = [
                    pv.get('value') for pv in field.get('picklistValues', []) 
                    if pv.get('active')
                ]
            
            fields.append(field_info)
    
    return fields

def get_object_describe(instance_url, access_token, object_name):
    """Get full describe information for an object"""
    endpoint = f'/services/data/v58.0/sobjects/{object_name}/describe/'
    response = make_api_request(instance_url, access_token, endpoint)
    
    # Simplify the response to include only relevant information
    object_info = {
        'name': response.get('name'),
        'label': response.get('label'),
        'fields': [],
        'relationships': []
    }
    
    # Process fields
    for field in response.get('fields', []):
        if field.get('createable'):
            field_info = {
                'name': field.get('name'),
                'label': field.get('label'),
                'type': field.get('type'),
                'required': field.get('nillable') is False and not field.get('defaultedOnCreate'),
                'unique': field.get('unique', False),
                'custom': field.get('custom', False),
                'updateable': field.get('updateable', False),
                'defaultValue': field.get('defaultValue')
            }
            
            # Add reference information if it's a lookup/master-detail
            if field.get('type') in ('reference', 'lookup', 'masterdetail'):
                field_info['referenceTo'] = field.get('referenceTo', [])
                field_info['relationshipName'] = field.get('relationshipName')
            
            # Add picklist values if applicable
            if field.get('type') in ('picklist', 'multipicklist'):
                field_info['picklistValues'] = [
                    pv.get('value') for pv in field.get('picklistValues', []) 
                    if pv.get('active')
                ]
                
            # Add length for string fields
            if field.get('type') in ('string', 'textarea'):
                field_info['length'] = field.get('length')
                
            # Add precision and scale for numeric fields
            if field.get('type') in ('double', 'currency', 'percent'):
                field_info['precision'] = field.get('precision')
                field_info['scale'] = field.get('scale')
            
            object_info['fields'].append(field_info)
    
    # Add relationship information
    for child_rel in response.get('childRelationships', []):
        rel_info = {
            'childObject': child_rel.get('childSObject'),
            'field': child_rel.get('field'),
            'relationshipName': child_rel.get('relationshipName')
        }
        object_info['relationships'].append(rel_info)
    
    return object_info

def insert_records(instance_url, access_token, object_name, records):
    """Insert multiple records using composite API"""
    # Using Composite API to insert multiple records in a single request
    endpoint = '/services/data/v58.0/composite/sobjects'
    
    # Prepare data in the format required by the Composite API
    composite_request = {
        'allOrNone': False,
        'records': []
    }
    
    for record in records:
        record_data = {
            'attributes': {
                'type': object_name
            }
        }
        record_data.update(record)
        composite_request['records'].append(record_data)
    
    # Make the request
    response = make_api_request(
        instance_url, 
        access_token, 
        endpoint, 
        method='POST', 
        data=composite_request
    )
    
    # Process results
    results = {
        'success': 0,
        'failure': 0,
        'errors': [],
        'created_ids': []
    }
    
    for result in response:
        if result.get('success'):
            results['success'] += 1
            results['created_ids'].append(result.get('id'))
        else:
            results['failure'] += 1
            errors = result.get('errors', [])
            for error in errors:
                results['errors'].append({
                    'message': error.get('message'),
                    'fields': error.get('fields', []),
                    'statusCode': error.get('statusCode')
                })
    
    return results

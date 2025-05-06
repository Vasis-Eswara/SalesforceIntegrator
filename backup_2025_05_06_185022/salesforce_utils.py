import os
import json
import logging
import requests
import base64
import hashlib
import secrets
from urllib.parse import urlencode

try:
    from flask import session
except ImportError:
    # Mock session for non-Flask environments
    class MockSession(dict):
        def get(self, key, default=None):
            return self.get(key, default)
        def pop(self, key, default=None):
            return self.pop(key, default) if key in self else default
    session = MockSession()

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


# Attempt to auto-detect the appropriate Salesforce URL
SF_CLIENT_DOMAIN = os.environ.get('SALESFORCE_DOMAIN', '')

# If a specific client domain is provided, use it directly
if SF_CLIENT_DOMAIN and SF_CLIENT_DOMAIN.strip():
    # Check if it's already a full URL or just a domain
    domain = SF_CLIENT_DOMAIN.strip()
    if domain.startswith('http'):
        SF_LOGIN_URL = domain
    else:
        SF_LOGIN_URL = f"https://{domain}"
    logger.debug(f"Using custom Salesforce domain: {SF_LOGIN_URL}")
else:
    # Try production URL as default
    SF_LOGIN_URL = 'https://login.salesforce.com'
    logger.debug(f"Using production Salesforce login URL: {SF_LOGIN_URL}")

def generate_code_verifier():
    """Generate a code_verifier for PKCE"""
    code_verifier = secrets.token_urlsafe(64)[:128]
    return code_verifier

def generate_code_challenge(code_verifier):
    """Generate a code_challenge from the code_verifier"""
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip('=')
    return code_challenge

def get_auth_url():
    """Generate Salesforce OAuth authorization URL with PKCE"""
    # Check if Salesforce credentials are configured
    if not SF_CLIENT_ID:
        raise Exception("Salesforce Client ID not configured. Please set the SALESFORCE_CLIENT_ID environment variable.")
    
    # Generate PKCE code verifier and challenge
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    
    # Store code_verifier in session
    session['sf_code_verifier'] = code_verifier
    
    # Print all environmental variables and configuration
    logger.debug(f"Current login URL: {SF_LOGIN_URL}")
    logger.debug(f"Redirect URI: {SF_REDIRECT_URI}")
    logger.debug(f"Client ID: {SF_CLIENT_ID[:5]}...{SF_CLIENT_ID[-5:] if len(SF_CLIENT_ID) > 10 else ''}")
    logger.debug(f"Code verifier generated: {code_verifier[:10]}...")
    logger.debug(f"Code challenge generated: {code_challenge[:10]}...")
    
    # Try using the documented Salesforce flow parameters exactly
    params = {
        'client_id': SF_CLIENT_ID,
        'redirect_uri': SF_REDIRECT_URI,
        'response_type': 'code',
        'display': 'page',  # Force full page display
        'immediate': 'false',  # Don't attempt immediate authentication
        'scope': 'api refresh_token offline_access custom_permissions',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'prompt': 'login consent'  # Force login prompt and consent screen
    }
    # Log all parameters for debugging
    logger.debug(f"OAuth params: {params}")
    
    auth_url = f"{SF_LOGIN_URL}/services/oauth2/authorize?{urlencode(params)}"
    logger.debug(f"Generated auth URL with PKCE: {auth_url}")
    return auth_url

def get_access_token(code):
    """Exchange authorization code for access token using PKCE"""
    # Check if Salesforce credentials are configured
    if not SF_CLIENT_ID or not SF_CLIENT_SECRET:
        raise Exception("Salesforce client credentials not configured. Please set the SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET environment variables.")
    
    # Get code_verifier from session
    code_verifier = session.get('sf_code_verifier')
    if not code_verifier:
        raise Exception("Code verifier missing from session. Please restart the authentication process.")
    
    token_url = f"{SF_LOGIN_URL}/services/oauth2/token"
    
    # Construct payload with all required parameters
    payload = {
        'grant_type': 'authorization_code',
        'client_id': SF_CLIENT_ID,
        'client_secret': SF_CLIENT_SECRET,
        'redirect_uri': SF_REDIRECT_URI,
        'code': code,
        'code_verifier': code_verifier
    }
    
    # Log the request details (remove sensitive info from logs)
    sanitized_payload = payload.copy()
    sanitized_payload['client_secret'] = '[REDACTED]'
    sanitized_payload['code_verifier'] = f"{sanitized_payload['code_verifier'][:10]}...[REDACTED]"
    sanitized_payload['code'] = f"{sanitized_payload['code'][:10]}...[REDACTED]" if len(sanitized_payload['code']) > 10 else '[REDACTED]'
    logger.debug(f"Token request URL: {token_url}")
    logger.debug(f"Token request payload: {sanitized_payload}")
    
    # Clear the code_verifier from session once used
    session.pop('sf_code_verifier', None)
    
    response = None
    try:
        response = requests.post(token_url, data=payload)
        
        # Enhanced logging of all response details regardless of status code
        logger.debug(f"Token request response - Status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Response full body: {response.text}")
        
        # Special error handling for common Salesforce error codes
        if response.status_code != 200:
            logger.error(f"Token request failed with status code {response.status_code}")
            logger.error(f"Response headers: {dict(response.headers)}")
            logger.error(f"Response body: {response.text}")
            
            try:
                error_json = response.json()
                logger.error(f"Error details: {error_json}")
            except:
                logger.error("Could not parse error response as JSON")
            
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting access token: {str(e)}")
        if response is not None:
            logger.error(f"Response status code: {response.status_code}")
            logger.error(f"Response headers: {dict(response.headers)}")
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

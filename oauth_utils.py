"""
Clean Salesforce OAuth 2.0 Implementation
Authorization Code Grant Flow with PKCE
"""
import os
import secrets
import base64
import hashlib
import logging
import requests
from urllib.parse import urlencode
from flask import session

logger = logging.getLogger(__name__)

# Salesforce OAuth Configuration
SALESFORCE_CLIENT_ID = os.environ.get('SALESFORCE_CLIENT_ID')
SALESFORCE_CLIENT_SECRET = os.environ.get('SALESFORCE_CLIENT_SECRET')
SALESFORCE_REDIRECT_URI = os.environ.get('SALESFORCE_REDIRECT_URI', 'https://2dbf6f12-560a-4cb9-8ca7-c2cd30a7fe4e-00-2kbskpp6fbk9s.worf.replit.dev/salesforce/callback')
SALESFORCE_LOGIN_URL = os.environ.get('SALESFORCE_DOMAIN', 'login.salesforce.com')
if not SALESFORCE_LOGIN_URL.startswith('http'):
    SALESFORCE_LOGIN_URL = f'https://{SALESFORCE_LOGIN_URL}'

# Ensure no trailing slash
if SALESFORCE_LOGIN_URL.endswith('/'):
    SALESFORCE_LOGIN_URL = SALESFORCE_LOGIN_URL[:-1]

def validate_oauth_config():
    """Validate that OAuth configuration is properly set"""
    missing = []
    if not SALESFORCE_CLIENT_ID:
        missing.append('SALESFORCE_CLIENT_ID')
    if not SALESFORCE_CLIENT_SECRET:
        missing.append('SALESFORCE_CLIENT_SECRET')
    if not SALESFORCE_REDIRECT_URI:
        missing.append('SALESFORCE_REDIRECT_URI')
    
    if missing:
        raise Exception(f"Missing OAuth configuration: {', '.join(missing)}")
    
    logger.info(f"OAuth configuration validated. Login URL: {SALESFORCE_LOGIN_URL}")
    return True

def generate_pkce_pair():
    """Generate PKCE code verifier and challenge"""
    # Generate code verifier (43-128 characters)
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    # Generate code challenge
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    return code_verifier, code_challenge

def get_authorization_url():
    """Generate Salesforce OAuth authorization URL"""
    validate_oauth_config()
    
    # Generate PKCE parameters
    code_verifier, code_challenge = generate_pkce_pair()
    
    # Store code verifier in session
    session['oauth_code_verifier'] = code_verifier
    
    # OAuth parameters
    params = {
        'response_type': 'code',
        'client_id': SALESFORCE_CLIENT_ID,
        'redirect_uri': SALESFORCE_REDIRECT_URI,
        'scope': 'api refresh_token offline_access',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'prompt': 'login'
    }
    
    auth_url = f"{SALESFORCE_LOGIN_URL}/services/oauth2/authorize?{urlencode(params)}"
    logger.info(f"Generated authorization URL for client ID: {SALESFORCE_CLIENT_ID[:8]}...")
    
    return auth_url

def exchange_code_for_tokens(authorization_code):
    """Exchange authorization code for access and refresh tokens"""
    validate_oauth_config()
    
    # Get code verifier from session
    code_verifier = session.get('oauth_code_verifier')
    if not code_verifier:
        raise Exception("Code verifier not found in session. Please restart the OAuth flow.")
    
    # Clear code verifier from session
    session.pop('oauth_code_verifier', None)
    
    # Token exchange parameters
    data = {
        'grant_type': 'authorization_code',
        'client_id': SALESFORCE_CLIENT_ID,
        'client_secret': SALESFORCE_CLIENT_SECRET,
        'redirect_uri': SALESFORCE_REDIRECT_URI,
        'code': authorization_code,
        'code_verifier': code_verifier
    }
    
    token_url = f"{SALESFORCE_LOGIN_URL}/services/oauth2/token"
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        logger.info(f"Successfully exchanged code for tokens. Instance URL: {token_data.get('instance_url')}")
        
        return token_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Token exchange failed: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        raise Exception(f"Failed to exchange authorization code: {str(e)}")

def refresh_access_token(refresh_token):
    """Refresh an expired access token"""
    validate_oauth_config()
    
    data = {
        'grant_type': 'refresh_token',
        'client_id': SALESFORCE_CLIENT_ID,
        'client_secret': SALESFORCE_CLIENT_SECRET,
        'refresh_token': refresh_token
    }
    
    token_url = f"{SALESFORCE_LOGIN_URL}/services/oauth2/token"
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        logger.info("Successfully refreshed access token")
        
        return token_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Token refresh failed: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        raise Exception(f"Failed to refresh access token: {str(e)}")

def store_tokens_in_session(token_data):
    """Store OAuth tokens in Flask session"""
    session['sf_access_token'] = token_data.get('access_token')
    session['sf_refresh_token'] = token_data.get('refresh_token')
    session['sf_instance_url'] = token_data.get('instance_url')
    session['sf_id'] = token_data.get('id')
    
    # Extract org ID from the id field
    if token_data.get('id'):
        id_parts = token_data['id'].split('/')
        if len(id_parts) >= 2:
            session['sf_org_id'] = id_parts[-2]
            session['sf_user_id'] = id_parts[-1]
    
    logger.info("Tokens stored in session successfully")

def clear_session():
    """Clear all OAuth-related data from session"""
    oauth_keys = [
        'sf_access_token', 'sf_refresh_token', 'sf_instance_url',
        'sf_id', 'sf_org_id', 'sf_user_id', 'oauth_code_verifier',
        'salesforce_org_id', 'salesforce_instance_url', 'salesforce_access_token'
    ]
    
    for key in oauth_keys:
        session.pop(key, None)
    
    logger.info("OAuth session cleared")

def is_authenticated():
    """Check if user is currently authenticated"""
    return 'sf_access_token' in session and 'sf_instance_url' in session

def get_current_session_info():
    """Get current OAuth session information"""
    if not is_authenticated():
        return None
    
    return {
        'access_token': session.get('sf_access_token'),
        'refresh_token': session.get('sf_refresh_token'),
        'instance_url': session.get('sf_instance_url'),
        'org_id': session.get('sf_org_id'),
        'user_id': session.get('sf_user_id')
    }
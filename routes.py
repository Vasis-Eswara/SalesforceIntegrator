import os
import json
import logging
from urllib.parse import urlencode
from flask import render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta

from app import db
from models import SalesforceOrg, SchemaObject, SchemaField, GenerationJob

# Import both REST and SOAP utilities
from salesforce_utils import (
    get_auth_url, get_access_token, refresh_access_token, 
    get_salesforce_objects, get_object_fields, 
    get_object_describe, insert_records
)

# Import SOAP-based implementations
from salesforce_soap_utils import (
    login_with_username_password, get_salesforce_objects_soap,
    get_object_describe_soap, insert_records_soap
)

from openai_utils import generate_test_data_with_gpt
from salesforce_config_utils import analyze_prompt_for_configuration, apply_configuration

logger = logging.getLogger(__name__)

def init_routes(app):
    
    @app.route('/')
    def index():
        """Homepage with connection status and navigation"""
        sf_connected = 'salesforce_org_id' in session
        return render_template('index.html', sf_connected=sf_connected)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Salesforce login page with both OAuth and direct SOAP login options"""
        if request.method == 'POST':
            login_type = request.form.get('login_type')
            
            # Direct login with username and password via SOAP API
            if login_type == 'direct':
                username = request.form.get('username')
                password = request.form.get('password')
                security_token = request.form.get('security_token', '')
                
                if not username or not password:
                    flash('Username and password are required', 'danger')
                    return redirect(url_for('login'))
                
                try:
                    # Attempt login with username/password via SOAP API
                    logger.debug(f"Attempting SOAP login for username: {username}")
                    login_result = login_with_username_password(username, password, security_token)
                    
                    # Store connection in database
                    sf_org = SalesforceOrg(
                        instance_url=login_result.get('instance_url'),
                        access_token=login_result.get('access_token'),
                        org_id=login_result.get('user_info', {}).get('org_id'),
                        user_id=login_result.get('user_info', {}).get('user_id')
                    )
                    
                    db.session.add(sf_org)
                    db.session.commit()
                    logger.debug(f"Saved Salesforce org connection to database with ID: {sf_org.id}")
                    
                    # Store in session
                    session['salesforce_org_id'] = sf_org.id
                    session['salesforce_instance_url'] = sf_org.instance_url
                    session['salesforce_access_token'] = sf_org.access_token
                    
                    flash('Successfully connected to Salesforce via SOAP API', 'success')
                    return redirect(url_for('schema'))
                    
                except Exception as e:
                    logger.error(f"SOAP login error: {str(e)}")
                    flash(f'Error connecting to Salesforce: {str(e)}', 'danger')
                    return redirect(url_for('login'))
                    
        # GET request - show login form
        return render_template('login.html')
    
    @app.route('/salesforce/auth')
    def salesforce_auth():
        """Initiate Salesforce OAuth flow"""
        try:
            auth_url = get_auth_url()
            return redirect(auth_url)
        except Exception as e:
            logger.error(f"Error initiating Salesforce auth: {str(e)}")
            flash(f'Error connecting to Salesforce: {str(e)}', 'danger')
            return redirect(url_for('login'))
    
    @app.route('/salesforce/callback')
    @app.route('/salesforce/callback/', endpoint='salesforce_callback_slash') # Handle trailing slash variant
    @app.route('/services/oauth2/success') # Add support for direct Salesforce callback URL
    def salesforce_callback():
        """Handle Salesforce OAuth callback"""
        # Log all request information to help debug
        logger.debug(f"Callback received. Request URL: {request.url}")
        logger.debug(f"Request args: {request.args}")
        logger.debug(f"Request method: {request.method}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        logger.debug(f"Session contents: {session}")
        logger.debug(f"Current Salesforce Login URL: {os.environ.get('SALESFORCE_DOMAIN')}")
        
        # Log the PKCE code verifier from session
        if 'sf_code_verifier' in session:
            logger.debug(f"PKCE code_verifier found in session: {session['sf_code_verifier'][:10]}...")
        else:
            logger.debug("No PKCE code_verifier found in session")
            # Re-initialize auth flow if code verifier is missing
            flash('Authentication session expired. Please try connecting again.', 'warning')
            return redirect(url_for('salesforce_auth'))
        
        code = request.args.get('code')
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        
        # Check for error first
        if error:
            error_msg = f"Authentication failed: {error}. {error_description}" if error_description else f"Authentication failed: {error}"
            logger.error(error_msg)
            flash(error_msg, 'danger')
            return redirect(url_for('login'))
        
        if not code:
            logger.error("No authorization code received in callback")
            flash('Authentication failed: No authorization code received', 'danger')
            return redirect(url_for('login'))
        
        try:
            # Exchange code for token
            logger.debug(f"Attempting to exchange code for token. Code starts with: {code[:10]}...")
            token_data = get_access_token(code)
            
            # Log token response (sanitized)
            logger.debug(f"Token response received with keys: {token_data.keys() if token_data else 'None'}")
            
            if not token_data or 'access_token' not in token_data:
                logger.error(f"Failed to obtain access token. Response: {token_data}")
                flash('Failed to obtain access token from Salesforce', 'danger')
                return redirect(url_for('login'))
            
            # Log successful token exchange
            logger.debug(f"Successfully obtained access token. Instance URL: {token_data.get('instance_url')}")
            logger.debug(f"Token type: {token_data.get('token_type')}")
            logger.debug(f"Refresh token obtained: {'Yes' if 'refresh_token' in token_data else 'No'}")
            
            # Store connection in database
            sf_org = SalesforceOrg(
                instance_url=token_data.get('instance_url'),
                access_token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                org_id=token_data.get('id', '').split('/')[-2] if 'id' in token_data else None,
                user_id=token_data.get('id', '').split('/')[-1] if 'id' in token_data else None
            )
            
            db.session.add(sf_org)
            db.session.commit()
            logger.debug(f"Saved Salesforce org connection to database with ID: {sf_org.id}")
            
            # Store in session
            session['salesforce_org_id'] = sf_org.id
            session['salesforce_instance_url'] = sf_org.instance_url
            session['salesforce_access_token'] = sf_org.access_token
            
            flash('Successfully connected to Salesforce', 'success')
            return redirect(url_for('schema'))
            
        except Exception as e:
            logger.error(f"Error during Salesforce callback: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            flash(f'Error connecting to Salesforce: {str(e)}', 'danger')
            return redirect(url_for('login'))
    
    @app.route('/logout')
    def logout():
        """Clear Salesforce connection from session"""
        session.pop('salesforce_org_id', None)
        session.pop('salesforce_instance_url', None)
        session.pop('salesforce_access_token', None)
        flash('Disconnected from Salesforce', 'info')
        return redirect(url_for('index'))
    
    @app.route('/schema')
    def schema():
        """Show Salesforce schema objects"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        try:
            # Get Salesforce connection
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Check if token refresh is needed
            if sf_org.updated_at < datetime.utcnow() - timedelta(minutes=55):
                if sf_org.refresh_token:
                    token_data = refresh_access_token(sf_org.refresh_token)
                    sf_org.access_token = token_data.get('access_token')
                    sf_org.updated_at = datetime.utcnow()
                    db.session.commit()
                    session['salesforce_access_token'] = sf_org.access_token
            
            # Get objects from Salesforce - try REST API first
            try:
                objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Successfully retrieved {len(objects)} objects via REST API")
            except Exception as rest_error:
                # If REST API fails, try SOAP API as fallback
                logger.warning(f"REST API failed, falling back to SOAP: {str(rest_error)}")
                objects = get_salesforce_objects_soap(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Successfully retrieved {len(objects)} objects via SOAP API")
            
            return render_template('schema.html', objects=objects)
            
        except Exception as e:
            logger.error(f"Error fetching schema: {str(e)}")
            flash(f'Error retrieving Salesforce schema: {str(e)}', 'danger')
            return redirect(url_for('index'))
    
    @app.route('/schema/<object_name>')
    def object_detail(object_name):
        """Show details of a specific Salesforce object"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Get object describe info - try REST API first
            try:
                object_info = get_object_describe(sf_org.instance_url, sf_org.access_token, object_name)
                logger.debug(f"Successfully retrieved object details for {object_name} via REST API")
            except Exception as rest_error:
                # If REST API fails, try SOAP API as fallback
                logger.warning(f"REST API failed for object detail, falling back to SOAP: {str(rest_error)}")
                object_info = get_object_describe_soap(sf_org.instance_url, sf_org.access_token, object_name)
                logger.debug(f"Successfully retrieved object details for {object_name} via SOAP API")
            
            return jsonify(object_info)
            
        except Exception as e:
            logger.error(f"Error fetching object detail: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/generate', methods=['GET', 'POST'])
    def generate():
        """Generate test data for a Salesforce object"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            object_name = request.form.get('object_name')
            record_count = int(request.form.get('record_count', 5))
            
            if not object_name:
                flash('Please select an object', 'warning')
                return redirect(url_for('generate'))
            
            try:
                sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
                
                # Get object describe info - try REST API first, then SOAP as fallback
                try:
                    object_info = get_object_describe(sf_org.instance_url, sf_org.access_token, object_name)
                    logger.debug(f"Successfully retrieved object details for {object_name} via REST API")
                except Exception as rest_error:
                    logger.warning(f"REST API failed for object detail, falling back to SOAP: {str(rest_error)}")
                    object_info = get_object_describe_soap(sf_org.instance_url, sf_org.access_token, object_name)
                    logger.debug(f"Successfully retrieved object details for {object_name} via SOAP API")
                
                # Create job record
                job = GenerationJob(
                    org_id=sf_org.org_id,
                    object_name=object_name,
                    record_count=record_count,
                    status='processing'
                )
                db.session.add(job)
                db.session.commit()
                
                # Generate data with GPT
                generated_data = generate_test_data_with_gpt(object_info, record_count)
                
                # Insert records to Salesforce - try REST API first, then SOAP as fallback
                try:
                    results = insert_records(sf_org.instance_url, sf_org.access_token, object_name, generated_data)
                    logger.debug(f"Successfully inserted {len(generated_data)} records via REST API")
                except Exception as rest_error:
                    logger.warning(f"REST API failed for record insertion, falling back to SOAP: {str(rest_error)}")
                    results = insert_records_soap(sf_org.instance_url, sf_org.access_token, object_name, generated_data)
                    logger.debug(f"Successfully inserted {len(generated_data)} records via SOAP API")
                
                # Update job with results
                job.status = 'completed'
                job.results = json.dumps(results)
                job.completed_at = datetime.utcnow()
                db.session.commit()
                
                flash(f'Successfully generated and inserted {record_count} records for {object_name}', 'success')
                return render_template('generate.html', job=job, results=results, object_name=object_name)
                
            except Exception as e:
                logger.error(f"Error generating data: {str(e)}")
                flash(f'Error generating data: {str(e)}', 'danger')
                return redirect(url_for('generate'))
        
        # GET request - show form
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
            return render_template('generate.html', objects=objects)
            
        except Exception as e:
            logger.error(f"Error fetching objects: {str(e)}")
            flash(f'Error retrieving Salesforce objects: {str(e)}', 'danger')
            return redirect(url_for('index'))
    
    @app.route('/configure', methods=['GET', 'POST'])
    def configure():
        """Configure Salesforce with natural language prompts"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
            
        # Check if OpenAI API key is configured
        if not app.config.get('OPENAI_API_KEY'):
            flash('OpenAI API key not configured. Please add your API key to use this feature.', 'warning')
        
        # Handle POST request (form submission)
        if request.method == 'POST':
            prompt = request.form.get('prompt', '')
            
            if not prompt:
                flash('Please enter a prompt', 'warning')
                return redirect(url_for('configure'))
                
            try:
                # Get Salesforce connection
                sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
                
                # Get org schema information for context
                objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                
                # Simplified org info for context
                org_info = {
                    'objects': objects
                }
                
                # Analyze prompt to determine configuration
                config = analyze_prompt_for_configuration(prompt, org_info)
                
                if 'error' in config:
                    flash(f'Error analyzing prompt: {config["error"]}', 'danger')
                    return render_template('configure.html', prompt=prompt, results={
                        'success': False,
                        'message': config['error'],
                        'details': config
                    })
                
                # Return the configuration for review
                return render_template('configure.html', prompt=prompt, results={
                    'success': True,
                    'message': 'Configuration generated successfully. Please review before applying.',
                    'details': config
                })
                
            except Exception as e:
                logger.error(f"Error configuring Salesforce: {str(e)}")
                flash(f'Error configuring Salesforce: {str(e)}', 'danger')
                return render_template('configure.html', prompt=prompt, results={
                    'success': False,
                    'message': str(e),
                    'details': {'error': str(e)}
                })
        
        # GET request - show form
        return render_template('configure.html')
    
    @app.route('/apply-config', methods=['POST'])
    def apply_config():
        """Apply a generated configuration to Salesforce"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
            
        try:
            # Get Salesforce connection
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Get the configuration from the form
            config_json = request.form.get('configuration', '')
            if not config_json:
                flash('No configuration provided', 'warning')
                return redirect(url_for('configure'))
                
            config = json.loads(config_json)
            
            # Apply the configuration
            result = apply_configuration(sf_org.instance_url, sf_org.access_token, config)
            
            if 'success' in result and result['success']:
                flash('Configuration applied successfully', 'success')
            else:
                flash(f'Error applying configuration: {result["message"] if "message" in result else "Unknown error"}', 'danger')
                
            # Return to configure page with the result
            return render_template('configure.html', results={
                'success': result['success'] if 'success' in result else False,
                'message': result['message'] if 'message' in result else 'Configuration applied.',
                'details': result
            })
            
        except Exception as e:
            logger.error(f"Error applying configuration: {str(e)}")
            flash(f'Error applying configuration: {str(e)}', 'danger')
            return redirect(url_for('configure'))
            
    @app.route('/api/chat', methods=['POST'])
    def chat():
        """Conversational endpoint for GPT interaction"""
        if 'salesforce_org_id' not in session:
            return jsonify({'error': 'Not connected to Salesforce'}), 401
        
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        try:
            # Parse user intent and execute appropriate action
            # This is a simplified version - in a real app, we'd use GPT to parse intent
            response = {
                'message': 'I understand you want to work with Salesforce data. Please use the interface to select objects and generate data.'
            }
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"Error in chat endpoint: {str(e)}")
            return jsonify({'error': str(e)}), 500

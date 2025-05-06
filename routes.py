import os
import json
import logging
from urllib.parse import urlencode
from flask import render_template, request, redirect, url_for, session, jsonify, flash, send_file
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

from app import db
from models import SalesforceOrg, SchemaObject, SchemaField, GenerationJob, SalesforceCredential

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
from excel_utils import generate_object_template, process_excel_configuration

logger = logging.getLogger(__name__)

def init_routes(app):
    
    # Helper function to get org information for templates
    def get_org_info():
        """Get Salesforce org information for templates"""
        org_info = {
            'connected': False,
            'name': None,
            'instance': None,
            'id': None
        }
        
        if 'salesforce_org_id' in session:
            try:
                sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
                if sf_org:
                    org_info['connected'] = True
                    # Extract org name from instance URL (simplified)
                    instance_parts = sf_org.instance_url.split('.')
                    if len(instance_parts) >= 2:
                        org_info['name'] = instance_parts[0].replace('https://', '')
                    org_info['instance'] = sf_org.instance_url
                    org_info['id'] = sf_org.org_id
            except Exception as e:
                logger.error(f"Error getting org info: {str(e)}")
        
        return org_info

    @app.route('/')
    def index():
        """Homepage with connection status and navigation"""
        sf_connected = 'salesforce_org_id' in session
        org_info = get_org_info()
        return render_template('index.html', sf_connected=sf_connected, org_info=org_info)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Salesforce login page with multiple connection options"""
        if request.method == 'POST':
            login_type = request.form.get('login_type')
            
            # Direct login with username and password via SOAP API
            if login_type == 'direct':
                username = request.form.get('username')
                password = request.form.get('password')
                security_token = request.form.get('security_token', '')
                remember = request.form.get('remember') == 'on'
                name = request.form.get('connection_name', f"Connection {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                sandbox = request.form.get('sandbox') == 'on'
                
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
                    
                    # If remember is checked, save credentials for future use
                    if remember:
                        try:
                            # Check if credentials already exist
                            existing_cred = SalesforceCredential.query.filter_by(username=username).first()
                            
                            if existing_cred:
                                # Update existing credentials
                                existing_cred.set_password(password)
                                existing_cred.security_token = security_token
                                existing_cred.sandbox = sandbox
                                existing_cred.last_used = datetime.utcnow()
                                existing_cred.name = name
                                db.session.commit()
                                flash(f'Updated saved credentials for {username}', 'info')
                            else:
                                # Create new credentials
                                cred = SalesforceCredential(username=username, name=name, sandbox=sandbox)
                                cred.set_password(password)
                                cred.security_token = security_token
                                cred.last_used = datetime.utcnow()
                                
                                # If this is the first credential, make it the default
                                if SalesforceCredential.query.count() == 0:
                                    cred.default = True
                                    
                                db.session.add(cred)
                                db.session.commit()
                                flash(f'Saved credentials for future use', 'info')
                        except Exception as e:
                            logger.error(f"Error saving credentials: {str(e)}")
                            # Non-blocking error - just log it
                            flash(f'Note: Could not save credentials for future use', 'warning')
                    
                    flash('Successfully connected to Salesforce via SOAP API', 'success')
                    return redirect(url_for('combined'))
                    
                except Exception as e:
                    logger.error(f"SOAP login error: {str(e)}")
                    flash(f'Error connecting to Salesforce: {str(e)}', 'danger')
                    return redirect(url_for('login'))
            
            # Login with saved credentials
            elif login_type == 'saved':
                credential_id = request.form.get('credential_id')
                
                if not credential_id:
                    flash('Please select a saved connection', 'warning')
                    return redirect(url_for('login'))
                
                try:
                    # Get the credential
                    cred = SalesforceCredential.query.get(credential_id)
                    if not cred:
                        flash('Selected connection not found', 'danger')
                        return redirect(url_for('login'))
                    
                    # We need to decrypt the password - it's done automatically when we call login
                    # Try to login with the saved credentials
                    logger.debug(f"Attempting SOAP login with saved credentials for {cred.username}")
                    
                    # Get the password from the form if one-time password is provided
                    password = request.form.get('one_time_password')
                    
                    # Use the saved credentials
                    login_result = None
                    if password:  # Use one-time password if provided
                        login_result = login_with_username_password(cred.username, password, cred.security_token)
                    else:  # Use saved password
                        # We'll need to retrieve the actual password (this is a simplified example)
                        # In a real app, you would need to securely retrieve and decrypt the password
                        # For this example, we'll show a message that we can't use the saved password directly
                        flash('For security reasons, please enter your password', 'warning')
                        return redirect(url_for('login'))
                    
                    # Store connection in database
                    sf_org = SalesforceOrg(
                        instance_url=login_result.get('instance_url'),
                        access_token=login_result.get('access_token'),
                        org_id=login_result.get('user_info', {}).get('org_id'),
                        user_id=login_result.get('user_info', {}).get('user_id')
                    )
                    
                    db.session.add(sf_org)
                    db.session.commit()
                    
                    # Update last used timestamp
                    cred.last_used = datetime.utcnow()
                    db.session.commit()
                    
                    # Store in session
                    session['salesforce_org_id'] = sf_org.id
                    session['salesforce_instance_url'] = sf_org.instance_url
                    session['salesforce_access_token'] = sf_org.access_token
                    
                    flash(f'Successfully connected to Salesforce using saved credentials', 'success')
                    return redirect(url_for('combined'))
                    
                except Exception as e:
                    logger.error(f"Error using saved credentials: {str(e)}")
                    flash(f'Error connecting to Salesforce: {str(e)}', 'danger')
                    return redirect(url_for('login'))
                
        # GET request - show login form with saved credentials
        saved_credentials = SalesforceCredential.query.order_by(SalesforceCredential.last_used.desc().nullslast()).all()
        default_credential = SalesforceCredential.query.filter_by(default=True).first()
        org_info = get_org_info()
        
        return render_template('login.html', 
                           saved_credentials=saved_credentials,
                           default_credential=default_credential,
                           org_info=org_info)
    
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
            return redirect(url_for('combined'))
            
        except Exception as e:
            logger.error(f"Error during Salesforce callback: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            flash(f'Error connecting to Salesforce: {str(e)}', 'danger')
            return redirect(url_for('login'))
    
    @app.route('/credentials', methods=['GET', 'POST', 'DELETE'])
    def credentials():
        """Manage saved Salesforce credentials"""
        if request.method == 'POST':
            # Handle form submissions for adding or updating credentials
            action = request.form.get('action')
            
            if action == 'update':
                # Update existing credential
                credential_id = request.form.get('credential_id')
                if not credential_id:
                    flash('No credential selected for update', 'danger')
                    return redirect(url_for('credentials'))
                    
                cred = SalesforceCredential.query.get(credential_id)
                if not cred:
                    flash('Credential not found', 'danger')
                    return redirect(url_for('credentials'))
                    
                # Update fields
                cred.name = request.form.get('name', cred.name)
                cred.sandbox = request.form.get('sandbox') == 'on'
                
                # If password provided, update it
                password = request.form.get('password')
                if password:
                    cred.set_password(password)
                    
                # Update security token if provided
                security_token = request.form.get('security_token')
                if security_token is not None:  # Empty string is valid (no security token)
                    cred.security_token = security_token
                    
                # Set as default if requested
                if request.form.get('default') == 'on':
                    cred.set_default()
                    
                db.session.commit()
                flash('Credential updated successfully', 'success')
                return redirect(url_for('credentials'))
                
            elif action == 'add':
                # Add new credential
                username = request.form.get('username')
                password = request.form.get('password')
                name = request.form.get('name')
                security_token = request.form.get('security_token', '')
                sandbox = request.form.get('sandbox') == 'on'
                default = request.form.get('default') == 'on'
                
                if not username or not password or not name:
                    flash('Name, username and password are required', 'danger')
                    return redirect(url_for('credentials'))
                    
                # Check if username already exists
                existing = SalesforceCredential.query.filter_by(username=username).first()
                if existing:
                    flash(f'A credential with username {username} already exists', 'warning')
                    return redirect(url_for('credentials'))
                    
                # Create new credential
                cred = SalesforceCredential(username=username, name=name, sandbox=sandbox)
                cred.set_password(password)
                cred.security_token = security_token
                
                db.session.add(cred)
                db.session.commit()
                
                # Set as default if requested or if it's the only credential
                if default or SalesforceCredential.query.count() == 1:
                    cred.set_default()
                    
                flash('New credential added successfully', 'success')
                return redirect(url_for('credentials'))
                
            elif action == 'delete':
                # Delete credential
                credential_id = request.form.get('credential_id')
                if not credential_id:
                    flash('No credential selected for deletion', 'danger')
                    return redirect(url_for('credentials'))
                    
                cred = SalesforceCredential.query.get(credential_id)
                if not cred:
                    flash('Credential not found', 'danger')
                    return redirect(url_for('credentials'))
                    
                # If this is the default credential, find another to make default
                if cred.default and SalesforceCredential.query.count() > 1:
                    next_default = SalesforceCredential.query.filter(SalesforceCredential.id != cred.id).first()
                    if next_default:
                        next_default.default = True
                        
                db.session.delete(cred)
                db.session.commit()
                flash('Credential deleted successfully', 'success')
                return redirect(url_for('credentials'))
                
        # GET request - show all credentials
        credentials = SalesforceCredential.query.order_by(SalesforceCredential.name).all()
        org_info = get_org_info()
        return render_template('credentials.html', credentials=credentials, org_info=org_info)
    
    @app.route('/logout')
    def logout():
        """Clear Salesforce connection from session"""
        session.pop('salesforce_org_id', None)
        session.pop('salesforce_instance_url', None)
        session.pop('salesforce_access_token', None)
        flash('Disconnected from Salesforce', 'info')
        return redirect(url_for('index'))
    
    # Schema route has been removed - functionality now available in the combined page
    
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
    
    @app.route('/combined', methods=['GET', 'POST'])
    def combined():
        """Combined schema viewer and data generation page"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        # Handle generation results display
        job = None
        results = None
        object_name = None
        
        if request.method == 'POST':
            # Process data generation request the same way as in the generate route
            return generate()
        
        # GET request - show combined interface
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
            return render_template('generate_with_schema.html', objects=objects,
                                  job=job, results=results, object_name=object_name)
        except Exception as e:
            logger.error(f"Error fetching objects: {str(e)}")
            flash(f'Error retrieving Salesforce objects: {str(e)}', 'danger')
            return redirect(url_for('index'))

    @app.route('/generate', methods=['GET', 'POST'])
    def generate():
        """Generate test data for a Salesforce object"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            object_name = request.form.get('object_name')
            record_count = int(request.form.get('record_count', 5))
            nlp_requirements = request.form.get('nlp_requirements', '')
            
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
                
                # Add NLP requirements if provided
                if nlp_requirements:
                    logger.info(f"Natural language requirements for {object_name}: {nlp_requirements}")
                    # Add the NLP requirements to the object_info for processing by GPT
                    if isinstance(object_info, dict):
                        object_info['nlp_requirements'] = nlp_requirements
                    
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
                
                # Check the referer to determine return page
                referer = request.headers.get('Referer', '')
                if 'combined' in referer:
                    # If coming from combined view, return to that view with results
                    sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
                    objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                    return render_template('generate_with_schema.html', objects=objects, job=job, results=results, object_name=object_name)
                else:
                    # Otherwise return to the standard generate page
                    return render_template('generate.html', job=job, results=results, object_name=object_name)
                
            except Exception as e:
                logger.error(f"Error generating data: {str(e)}")
                flash(f'Error generating data: {str(e)}', 'danger')
                # Check the referer to determine return page
                referer = request.headers.get('Referer', '')
                if 'combined' in referer:
                    return redirect(url_for('combined'))
                else:
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
        # Check if the user is logged in
        is_logged_in = 'salesforce_org_id' in session
        logger.debug(f"Configure page access - logged in: {is_logged_in}")
        
        # Check if OpenAI API key is configured
        has_openai_key = bool(app.config.get('OPENAI_API_KEY'))
        if not has_openai_key:
            flash('OpenAI API key not configured. Please add your API key to use this feature.', 'warning')
        
        # Handle POST request (form submission)
        if request.method == 'POST':
            prompt = request.form.get('prompt', '')
            
            if not prompt:
                flash('Please enter a prompt', 'warning')
                return redirect(url_for('configure'))
                
            # Ensure user is logged in before processing the prompt
            if not is_logged_in:
                flash('Please connect to Salesforce first to use this feature', 'warning')
                return render_template('configure.html', is_logged_in=is_logged_in, has_openai_key=has_openai_key)
                
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
                    }, is_logged_in=is_logged_in, has_openai_key=has_openai_key)
                
                # Return the configuration for review
                return render_template('configure.html', prompt=prompt, results={
                    'success': True,
                    'message': 'Configuration generated successfully. Please review before applying.',
                    'details': config
                }, is_logged_in=is_logged_in, has_openai_key=has_openai_key)
                
            except Exception as e:
                logger.error(f"Error configuring Salesforce: {str(e)}")
                flash(f'Error configuring Salesforce: {str(e)}', 'danger')
                return render_template('configure.html', prompt=prompt, results={
                    'success': False,
                    'message': str(e),
                    'details': {'error': str(e)}
                }, is_logged_in=is_logged_in, has_openai_key=has_openai_key)
        
        # GET request - show form
        org_info = get_org_info()
        return render_template('configure.html', is_logged_in=is_logged_in, has_openai_key=has_openai_key, org_info=org_info)
    
    @app.route('/excel-template')
    def excel_template():
        """Download Excel template for Salesforce configuration"""
        try:
            # Generate the template
            template_path = generate_object_template()
            return send_file(template_path, as_attachment=True)
        except Exception as e:
            logger.error(f"Error generating Excel template: {str(e)}")
            flash(f'Error generating Excel template: {str(e)}', 'danger')
            return redirect(url_for('configure'))
    
    @app.route('/upload-excel', methods=['POST'])
    def upload_excel():
        """Upload and process Excel configuration file"""
        # Ensure the user is logged in
        is_logged_in = 'salesforce_org_id' in session
        if not is_logged_in:
            logger.warning("User attempted to upload Excel config without being logged in")
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
            
        has_openai_key = bool(os.environ.get('OPENAI_API_KEY'))
        
        if 'config_file' not in request.files:
            flash('No file part', 'warning')
            return redirect(url_for('configure'))
            
        file = request.files['config_file']
        if file.filename == '':
            flash('No selected file', 'warning')
            return redirect(url_for('configure'))
            
        try:
            # Save the uploaded file temporarily
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            if not os.path.exists(uploads_dir):
                os.makedirs(uploads_dir)
                
            file_path = os.path.join(uploads_dir, secure_filename(file.filename))
            file.save(file_path)
            
            # Process the file
            config = process_excel_configuration(file_path)
            
            # Clean up
            os.remove(file_path)
            
            org_info = get_org_info()
            return render_template('configure.html', prompt="Excel configuration", results={
                'success': True,
                'message': 'Excel configuration processed successfully. Please review before applying.',
                'details': config
            }, is_logged_in=is_logged_in, has_openai_key=has_openai_key, org_info=org_info)
            
        except Exception as e:
            logger.error(f"Error processing Excel configuration: {str(e)}")
            flash(f'Error processing Excel configuration: {str(e)}', 'danger')
            return render_template('configure.html', results={
                'success': False,
                'message': str(e),
                'details': {'error': str(e)}
            }, is_logged_in=is_logged_in, has_openai_key=has_openai_key)
    
    @app.route('/apply-config', methods=['POST'])
    def apply_config():
        """Apply a generated configuration to Salesforce"""
        # Ensure the user is logged in
        if 'salesforce_org_id' not in session:
            logger.warning("User attempted to apply configuration without being logged in")
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
            }, is_logged_in=True, has_openai_key=bool(app.config.get('OPENAI_API_KEY')))
            
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

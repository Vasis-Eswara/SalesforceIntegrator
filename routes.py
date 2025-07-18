import os
import json
import csv
import io
import logging
from urllib.parse import urlencode
from flask import render_template, request, redirect, url_for, session, jsonify, flash, send_file, Response
from markupsafe import Markup
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

from salesforce_soap_utils import (
    SalesforceSOAPClient, get_salesforce_objects_soap, 
    get_object_describe_soap, login_with_username_password
)

# Import SOAP-based implementations
from salesforce_soap_utils import (
    login_with_username_password, get_salesforce_objects_soap,
    get_object_describe_soap, insert_records_soap
)

from openai_utils import generate_test_data_with_gpt
from faker_utils import generate_test_data_with_faker, analyze_schema
from salesforce_config_utils import analyze_prompt_for_configuration, apply_configuration
from salesforce_metadata_client import create_metadata_client
from diagnostic_auth import diagnose_auth_issue, format_diagnostic_report
from excel_utils import generate_object_template, process_excel_configuration

logger = logging.getLogger(__name__)

def init_routes(app):
    
    def handle_unified_prompt(mode, unified_prompt, github_url, default_record_count, 
                            data_quality, preview_mode, respect_relationships):
        """Handle unified prompt interface processing for schema creation and bulk data generation"""
        from bulk_data_utils import BulkDataParser, GitHubConfigParser, validate_data_plan
        from comprehensive_config_parser import analyze_prompt_for_configuration
        
        sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
        results = {'status': 'success', 'actions': [], 'preview': {}, 'errors': []}
        
        try:
            # Handle GitHub configuration
            if github_url or mode == 'github':
                logger.info(f"Processing GitHub configuration from URL: {github_url}")
                github_parser = GitHubConfigParser()
                config_data = github_parser.parse_github_url(github_url)
                
                if config_data.get('objects'):
                    # Validate against available objects
                    available_objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                    available_names = [obj.get('name') for obj in available_objects]
                    
                    validated_plan = validate_data_plan(config_data, available_names)
                    results['preview'] = validated_plan
                    
                    if preview_mode:
                        results['message'] = "Configuration preview ready. Review and confirm to proceed."
                        return render_template('preview_confirmation.html', 
                                            preview=validated_plan, 
                                            original_config=config_data)
                    else:
                        # Execute the plan directly
                        execution_results = execute_bulk_data_plan(validated_plan, sf_org)
                        results.update(execution_results)
                        
                else:
                    results['errors'].append("No valid objects found in GitHub configuration")
            
            # Handle natural language prompt
            elif unified_prompt:
                logger.info(f"Processing natural language prompt: {unified_prompt[:100]}...")
                
                # Check if this is schema creation, data generation, or both
                prompt_lower = unified_prompt.lower()
                
                if 'create' in prompt_lower and ('object' in prompt_lower or 'field' in prompt_lower):
                    # Schema creation
                    config_actions = analyze_prompt_for_configuration(unified_prompt)
                    
                    if config_actions and config_actions.get('actions'):
                        # Apply schema changes
                        metadata_client = create_metadata_client(sf_org.instance_url, sf_org.access_token)
                        schema_results = apply_configuration(config_actions, metadata_client)
                        results['actions'].extend(schema_results.get('actions', []))
                        results['errors'].extend(schema_results.get('errors', []))
                
                if 'generate' in prompt_lower or 'create' in prompt_lower and 'record' in prompt_lower:
                    # Data generation
                    bulk_parser = BulkDataParser()
                    data_plan = bulk_parser.parse_prompt(unified_prompt)
                    
                    if data_plan.get('objects'):
                        # Validate against available objects
                        available_objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                        available_names = [obj.get('name') for obj in available_objects]
                        
                        validated_plan = validate_data_plan(data_plan, available_names)
                        
                        # Set default record counts if not specified
                        for obj_name, obj_config in validated_plan.get('objects', {}).items():
                            if not obj_config.get('record_count'):
                                obj_config['record_count'] = default_record_count
                        
                        results['preview'] = validated_plan
                        
                        if preview_mode:
                            results['message'] = "Data generation preview ready. Review and confirm to proceed."
                            return render_template('preview_confirmation.html', 
                                                preview=validated_plan, 
                                                original_prompt=unified_prompt)
                        else:
                            # Execute the plan directly
                            execution_results = execute_bulk_data_plan(validated_plan, sf_org)
                            results.update(execution_results)
                    else:
                        # Fallback: If no objects detected but it's a data generation request,
                        # show helpful guidance
                        results['errors'].append("I didn't detect specific Salesforce objects in your prompt. Try using formats like:")
                        results['errors'].append("• 'Generate 5 records for Account'")
                        results['errors'].append("• 'Create 10 Contacts'") 
                        results['errors'].append("• 'Insert 3 Opportunities'")
                        results['errors'].append("Or select an object from the sidebar and use the individual data generation features.")
                        
            else:
                results['errors'].append("No prompt or GitHub URL provided")
                
        except Exception as e:
            logger.error(f"Error processing unified prompt: {str(e)}")
            results['errors'].append(f"Processing error: {str(e)}")
            results['status'] = 'error'
        
        # Return results to template
        flash(f"Processed prompt with {len(results.get('actions', []))} actions and {len(results.get('errors', []))} errors", 
              'success' if results['status'] == 'success' else 'warning')
        
        # Get objects for template
        objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
        org_info = get_org_info()
        
        return render_template('generate_with_schema.html', 
                             objects=objects,
                             unified_results=results,
                             org_info=org_info,
                             search_query='')
    
    def execute_bulk_data_plan(plan, sf_org):
        """Execute a validated bulk data generation plan"""
        from intelligent_data_gen import IntelligentDataGenerator
        
        results = {'success': 0, 'failure': 0, 'created_ids': [], 'errors': []}
        
        try:
            # Initialize intelligent data generator
            generator = IntelligentDataGenerator(sf_org)
            
            # Process objects in execution order
            execution_order = plan.get('execution_order', list(plan.get('objects', {}).keys()))
            
            for object_name in execution_order:
                object_config = plan['objects'].get(object_name, {})
                record_count = object_config.get('record_count', 10)
                
                logger.info(f"Generating {record_count} records for {object_name}")
                
                # Generate data using intelligent generator
                generation_result = generator.generate_data(object_name, record_count)
                
                if generation_result.get('records'):
                    # Insert records
                    try:
                        insert_result = insert_records(sf_org.instance_url, sf_org.access_token, 
                                                     object_name, generation_result['records'])
                        results['success'] += len(insert_result.get('success', []))
                        results['failure'] += len(insert_result.get('errors', []))
                        results['created_ids'].extend(insert_result.get('success', []))
                        
                    except Exception as insert_error:
                        logger.error(f"Error inserting {object_name} records: {str(insert_error)}")
                        results['errors'].append(f"Failed to insert {object_name} records: {str(insert_error)}")
                        results['failure'] += record_count
                else:
                    results['errors'].append(f"No data generated for {object_name}")
                    results['failure'] += record_count
                    
        except Exception as e:
            logger.error(f"Error executing bulk data plan: {str(e)}")
            results['errors'].append(f"Execution error: {str(e)}")
        
        return results
    
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
    
    # =============================================================================
    # CLEAN SALESFORCE OAUTH 2.0 IMPLEMENTATION
    # =============================================================================
    
    @app.route('/login')
    def login():
        """Clean OAuth 2.0 login - redirect to Salesforce authorization"""
        try:
            from oauth_utils import get_authorization_url
            auth_url = get_authorization_url()
            return redirect(auth_url)
        except Exception as e:
            logger.error(f"OAuth login error: {str(e)}")
            flash(f'OAuth configuration error: {str(e)}', 'danger')
            return render_template('login_error.html', error=str(e))
    
    @app.route('/oauth/callback')
    @app.route('/salesforce/callback')
    def oauth_callback():
        """Handle OAuth callback from Salesforce"""
        from oauth_utils import exchange_code_for_tokens, store_tokens_in_session
        
        # Check for errors
        error = request.args.get('error')
        if error:
            error_description = request.args.get('error_description', '')
            logger.error(f"OAuth error: {error} - {error_description}")
            flash(f'Authentication failed: {error}', 'danger')
            return redirect(url_for('index'))
        
        # Get authorization code
        code = request.args.get('code')
        if not code:
            logger.error("No authorization code received")
            flash('Authentication failed: No authorization code received', 'danger')
            return redirect(url_for('index'))
        
        try:
            # Exchange code for tokens
            token_data = exchange_code_for_tokens(code)
            
            # Store tokens in session
            store_tokens_in_session(token_data)
            
            # Store in database for persistence
            from models import SalesforceOrg
            sf_org = SalesforceOrg(
                instance_url=token_data.get('instance_url'),
                access_token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                org_id=session.get('sf_org_id'),
                user_id=session.get('sf_user_id')
            )
            
            db.session.add(sf_org)
            db.session.commit()
            
            # Update session with database ID
            session['salesforce_org_id'] = sf_org.id
            
            flash('Successfully connected to Salesforce!', 'success')
            return redirect(url_for('combined'))
            
        except Exception as e:
            logger.error(f"Token exchange error: {str(e)}")
            flash(f'Authentication failed: {str(e)}', 'danger')
            return redirect(url_for('index'))
    
    @app.route('/legacy-login', methods=['GET', 'POST'])
    def legacy_login():
        """Legacy login page with multiple connection options (kept for compatibility)"""
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
                    
                    # Run diagnostic and provide detailed feedback
                    try:
                        diagnostic_results = diagnose_auth_issue(
                            username, 
                            password, 
                            security_token,
                            sandbox
                        )
                        diagnostic_html = format_diagnostic_report(diagnostic_results)
                        flash(Markup(diagnostic_html), 'danger')
                    except:
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
                    
                    # Run diagnostic and provide detailed feedback
                    try:
                        diagnostic_results = diagnose_auth_issue(
                            cred.username, 
                            password, 
                            cred.security_token,
                            cred.sandbox
                        )
                        diagnostic_html = format_diagnostic_report(diagnostic_results)
                        flash(Markup(diagnostic_html), 'danger')
                    except:
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
        from oauth_utils import clear_session
        clear_session()
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
    
    @app.route('/api/relationship-map/<object_name>')
    def advanced_relationship_map(object_name):
        """Generate advanced relationship mapping for complex object hierarchies"""
        if 'salesforce_org_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Get all objects to understand the complete hierarchy
            try:
                all_objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Retrieved {len(all_objects)} objects for relationship mapping")
            except Exception as rest_error:
                logger.warning(f"REST API failed for objects, falling back to SOAP: {str(rest_error)}")
                all_objects = get_salesforce_objects_soap(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Retrieved {len(all_objects)} objects via SOAP for relationship mapping")
            
            # Get primary object details
            try:
                primary_object = get_object_describe(sf_org.instance_url, sf_org.access_token, object_name)
            except Exception as rest_error:
                logger.warning(f"REST API failed for primary object, falling back to SOAP: {str(rest_error)}")
                primary_object = get_object_describe_soap(sf_org.instance_url, sf_org.access_token, object_name)
            
            # Build comprehensive relationship map
            relationship_map = {
                'object_name': object_name,
                'parent_relationships': [],
                'child_relationships': [],
                'sibling_relationships': [],
                'dependency_chain': [],
                'hierarchy_level': 0
            }
            
            # Analyze parent relationships (objects this one references)
            for field in primary_object.get('fields', []):
                if field.get('type') == 'reference' and field.get('referenceTo'):
                    for ref_obj in field['referenceTo']:
                        relationship_map['parent_relationships'].append({
                            'field_name': field['name'],
                            'field_label': field['label'],
                            'target_object': ref_obj,
                            'required': not field.get('nillable', True),
                            'relationship_type': 'lookup' if field.get('nillable', True) else 'master_detail'
                        })
            
            # Find child relationships (objects that reference this one)
            for obj in all_objects:
                try:
                    # Only check custom objects and key standard objects to avoid overwhelming the system
                    if obj.get('custom') or obj.get('name') in ['Account', 'Contact', 'Opportunity', 'Case', 'Lead']:
                        obj_details = get_object_describe(sf_org.instance_url, sf_org.access_token, obj['name'])
                        
                        for field in obj_details.get('fields', []):
                            if (field.get('type') == 'reference' and 
                                field.get('referenceTo') and 
                                object_name in field['referenceTo']):
                                
                                relationship_map['child_relationships'].append({
                                    'source_object': obj['name'],
                                    'source_object_label': obj['label'],
                                    'field_name': field['name'],
                                    'field_label': field['label'],
                                    'required': not field.get('nillable', True),
                                    'relationship_type': 'lookup' if field.get('nillable', True) else 'master_detail'
                                })
                except Exception as e:
                    # Skip objects that can't be described (insufficient permissions, etc.)
                    logger.debug(f"Skipping object {obj.get('name')} in relationship mapping: {str(e)}")
                    continue
            
            # Calculate hierarchy level and dependency chain
            relationship_map['hierarchy_level'] = len(relationship_map['parent_relationships'])
            
            # Build dependency chain (simplified)
            dependency_chain = []
            for parent_rel in relationship_map['parent_relationships']:
                if parent_rel['relationship_type'] == 'master_detail':
                    dependency_chain.append(parent_rel['target_object'])
            relationship_map['dependency_chain'] = dependency_chain
            
            logger.info(f"Generated relationship map for {object_name}: "
                       f"{len(relationship_map['parent_relationships'])} parents, "
                       f"{len(relationship_map['child_relationships'])} children")
            
            return jsonify(relationship_map)
            
        except Exception as e:
            logger.error(f"Error generating relationship map for {object_name}: {str(e)}")
            return jsonify({'error': str(e)}), 500
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/search-objects')
    def search_objects():
        """AJAX endpoint for real-time object search"""
        if 'salesforce_org_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        search_query = request.args.get('q', '').strip()
        
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Use the exact same logic as the working /combined route
            objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
            logger.debug(f"Successfully retrieved {len(objects)} objects via REST API")
            
            # Filter objects based on search query
            if search_query:
                objects = [obj for obj in objects if search_query.lower() in obj.get('label', '').lower()]
            
            # Return JSON response with filtered objects
            return jsonify({
                'objects': objects,
                'search_query': search_query,
                'total_count': len(objects)
            })
            
        except Exception as e:
            logger.error(f"Error in search_objects: {str(e)}")
            return jsonify({'error': str(e)}), 500

    # =============================================================================
    # BULK DATA INSERTION WITH NATURAL LANGUAGE & GITHUB CONFIG SUPPORT
    # =============================================================================

    @app.route('/bulk-data', methods=['GET', 'POST'])
    def bulk_data():
        """Bulk data creation with natural language and GitHub config support"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        org_info = get_org_info()
        
        if request.method == 'POST':
            mode = request.form.get('mode')  # 'natural' or 'github'
            
            if mode == 'natural':
                return handle_natural_language_bulk_data(request.form)
            elif mode == 'github':
                return handle_github_config_bulk_data(request.form)
            else:
                flash('Invalid data creation mode', 'danger')
                return redirect(url_for('bulk_data'))
        
        # GET request - show bulk data interface
        return render_template('bulk_data.html', org_info=org_info)
    
    def handle_natural_language_bulk_data(form_data):
        """Handle natural language bulk data creation"""
        from bulk_data_utils import BulkDataParser, validate_data_plan
        
        prompt = form_data.get('prompt', '').strip()
        if not prompt:
            flash('Please enter a data creation prompt', 'warning')
            return redirect(url_for('bulk_data'))
        
        try:
            # Parse natural language prompt
            parser = BulkDataParser()
            data_plan = parser.parse_prompt(prompt)
            
            # Get available objects for validation
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
            object_names = [obj['name'] for obj in objects]
            
            # Validate plan
            validation = validate_data_plan(data_plan, object_names)
            
            # Store plan in session for confirmation
            session['bulk_data_plan'] = data_plan
            session['bulk_data_validation'] = validation
            
            # Show confirmation page
            org_info = get_org_info()
            return render_template('bulk_data_confirm.html', 
                                 plan=data_plan, 
                                 validation=validation,
                                 prompt=prompt,
                                 mode='natural',
                                 org_info=org_info)
            
        except Exception as e:
            logger.error(f"Error parsing natural language prompt: {str(e)}")
            flash(f'Error parsing prompt: {str(e)}', 'danger')
            return redirect(url_for('bulk_data'))
    
    def handle_github_config_bulk_data(form_data):
        """Handle GitHub config bulk data creation"""
        from bulk_data_utils import GitHubConfigParser, validate_data_plan
        
        github_url = form_data.get('github_url', '').strip()
        if not github_url:
            flash('Please enter a GitHub URL', 'warning')
            return redirect(url_for('bulk_data'))
        
        try:
            # Parse GitHub config
            parser = GitHubConfigParser()
            data_plan = parser.parse_github_url(github_url)
            
            # Get available objects for validation
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
            object_names = [obj['name'] for obj in objects]
            
            # Validate plan
            validation = validate_data_plan(data_plan, object_names)
            
            # Store plan in session for confirmation
            session['bulk_data_plan'] = data_plan
            session['bulk_data_validation'] = validation
            
            # Show confirmation page
            org_info = get_org_info()
            return render_template('bulk_data_confirm.html', 
                                 plan=data_plan, 
                                 validation=validation,
                                 github_url=github_url,
                                 mode='github',
                                 org_info=org_info)
            
        except Exception as e:
            logger.error(f"Error parsing GitHub config: {str(e)}")
            flash(f'Error parsing GitHub config: {str(e)}', 'danger')
            return redirect(url_for('bulk_data'))
    
    @app.route('/bulk-data/execute', methods=['POST'])
    def execute_bulk_data():
        """Execute confirmed bulk data creation plan"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        # Get plan from session
        data_plan = session.get('bulk_data_plan')
        validation = session.get('bulk_data_validation')
        
        if not data_plan or not validation:
            flash('No data creation plan found. Please start over.', 'warning')
            return redirect(url_for('bulk_data'))
        
        if not validation['valid']:
            flash('Cannot execute invalid data plan. Please fix errors first.', 'danger')
            return redirect(url_for('bulk_data'))
        
        try:
            # Execute bulk data creation
            results = execute_data_plan(data_plan)
            
            # Clear plan from session
            session.pop('bulk_data_plan', None)
            session.pop('bulk_data_validation', None)
            
            flash(f'Successfully created {results["total_created"]} records across {len(results["objects"])} objects', 'success')
            
            # Show results
            org_info = get_org_info()
            return render_template('bulk_data_results.html', 
                                 results=results,
                                 plan=data_plan,
                                 org_info=org_info)
            
        except Exception as e:
            logger.error(f"Error executing bulk data creation: {str(e)}")
            flash(f'Error creating data: {str(e)}', 'danger')
            return redirect(url_for('bulk_data'))
    
    def execute_data_plan(data_plan):
        """Execute a validated data creation plan"""
        from faker_utils import generate_test_data_with_faker
        from intelligent_data_gen import IntelligentDataGenerator
        
        sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
        results = {
            'objects': {},
            'total_created': 0,
            'errors': [],
            'execution_order': data_plan['execution_order']
        }
        
        # Create connection object for intelligent generator
        sf_connection = type('SFConnection', (), {
            'access_token': sf_org.access_token,
            'instance_url': sf_org.instance_url
        })
        
        generator = IntelligentDataGenerator(sf_connection)
        
        # Execute in dependency order
        for object_name in data_plan['execution_order']:
            obj_config = data_plan['objects'][object_name]
            record_count = obj_config['count']
            
            try:
                logger.info(f"Creating {record_count} records for {object_name}")
                
                # Generate data using intelligent generator
                result = generator.generate_data(object_name, record_count)
                
                if result['success_count'] > 0:
                    results['objects'][object_name] = {
                        'created': result['success_count'],
                        'errors': result['errors'],
                        'records': result['records']
                    }
                    results['total_created'] += result['success_count']
                    logger.info(f"Successfully created {result['success_count']} {object_name} records")
                else:
                    error_msg = f"Failed to create {object_name} records: {'; '.join(result['errors'])}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
                
            except Exception as e:
                error_msg = f"Error creating {object_name} records: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        return results
    
    @app.route('/api/object/<object_name>/details')
    def api_object_details(object_name):
        """API endpoint to get detailed object schema information"""
        if 'salesforce_org_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
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
            
            return jsonify(object_info)
            
        except Exception as e:
            logger.error(f"Error getting object details for {object_name}: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/relationship-map/<object_name>')
    def api_relationship_map(object_name):
        """API endpoint to get object relationship mapping"""
        if 'salesforce_org_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Get object describe info
            try:
                object_info = get_object_describe(sf_org.instance_url, sf_org.access_token, object_name)
            except Exception as rest_error:
                object_info = get_object_describe_soap(sf_org.instance_url, sf_org.access_token, object_name)
            
            # Extract relationship information
            relationships = {
                'parents': [],
                'children': [],
                'related': []
            }
            
            if object_info and 'fields' in object_info:
                fields = object_info['fields']
                if isinstance(fields, str):
                    fields = json.loads(fields)
                
                for field in fields:
                    if field.get('type') == 'reference' and field.get('referenceTo'):
                        # This object references other objects (parents)
                        for ref_obj in field['referenceTo']:
                            if ref_obj not in relationships['parents']:
                                relationships['parents'].append(ref_obj)
            
            # For children and related objects, we'd need to query other objects
            # For now, we'll return the basic parent relationships
            # This could be enhanced to do more comprehensive relationship mapping
            
            return jsonify(relationships)
            
        except Exception as e:
            logger.error(f"Error getting relationship map for {object_name}: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/refresh-schema')
    def refresh_schema():
        """Refresh Salesforce schema on demand"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Clear any cached schema data
            # TODO: Implement schema caching and clearing
            
            # Re-fetch objects
            objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
            
            flash(f'Successfully refreshed schema. Found {len(objects)} objects.', 'success')
            
        except Exception as e:
            logger.error(f"Error refreshing schema: {str(e)}")
            flash(f'Error refreshing schema: {str(e)}', 'danger')
        
        return redirect(url_for('combined'))

    @app.route('/combined', methods=['GET', 'POST'])
    def combined():
        """Combined schema viewer and data generation page with server-side search"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        # Handle search query
        search_query = request.args.get('q', '').strip()
        
        # Handle generation results display
        job = None
        results = None
        object_name = None
        
        if request.method == 'POST':
            # New unified prompt interface
            mode = request.form.get('mode', 'auto')
            unified_prompt = request.form.get('prompt', '').strip()
            github_url = request.form.get('github_url', '').strip()
            default_record_count = int(request.form.get('default_record_count', 10))
            data_quality = request.form.get('data_quality', 'realistic')
            preview_mode = request.form.get('preview_mode') == 'on'
            respect_relationships = request.form.get('respect_relationships') == 'on'
            
            # Legacy support for old form data
            object_name = request.form.get('object_name')
            record_count = int(request.form.get('record_count', default_record_count))
            nlp_requirements = request.form.get('nlp_requirements', '')
            
            # Process unified prompt interface
            if unified_prompt or github_url:
                return handle_unified_prompt(
                    mode, unified_prompt, github_url, default_record_count,
                    data_quality, preview_mode, respect_relationships
                )
            
            # Legacy object-specific data generation
            if not object_name:
                flash('Please select an object or enter a prompt', 'warning')
                return redirect(url_for('combined'))
            
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
                    
                # Generate data with Faker instead of GPT
                try:
                    logger.debug(f"Generating data with Faker for {object_name}, record count: {record_count}")
                    
                    # Additional input validation and proper error handling
                    if not object_info:
                        logger.error(f"object_info is empty or None")
                        raise ValueError("No object schema information available")
                    
                    # Ensure object_info is either a dictionary or a properly formatted JSON string
                    if isinstance(object_info, dict):
                        # Verify the object_info has the required structure
                        if 'fields' not in object_info:
                            logger.error(f"object_info is missing required 'fields' key")
                            raise ValueError("The object schema is missing required field information")
                            
                    elif isinstance(object_info, str):
                        # Try to parse and validate JSON string
                        try:
                            parsed_info = json.loads(object_info)
                            if 'fields' not in parsed_info:
                                logger.error(f"Parsed object_info is missing required 'fields' key")
                                raise ValueError("The object schema is missing required field information")
                        except json.JSONDecodeError as je:
                            logger.error(f"object_info is not valid JSON: {je}")
                            raise ValueError(f"Invalid schema format: {str(je)}")
                    else:
                        logger.error(f"object_info is not a dictionary or valid JSON string: {type(object_info)}")
                        try:
                            # Try to convert to JSON string if possible
                            object_info = json.dumps(object_info)
                            logger.debug("Successfully converted object_info to JSON string")
                        except Exception as je:
                            logger.error(f"Failed to convert object_info to JSON: {je}")
                            raise ValueError(f"Schema information is in an unsupported format: {type(object_info)}")
                    
                    # Additional deep validation of the fields structure
                    if isinstance(object_info, dict) and 'fields' in object_info:
                        # Check if we need to fix the fields structure
                        fields = object_info['fields']
                        if isinstance(fields, str):
                            logger.warning("Fields is a string, attempting to fix")
                            try:
                                # Try to parse as JSON
                                parsed_fields = json.loads(fields)
                                if isinstance(parsed_fields, list):
                                    logger.info("Successfully converted fields string to list")
                                    object_info['fields'] = parsed_fields
                                else:
                                    logger.warning(f"Parsed fields is not a list: {type(parsed_fields)}")
                            except Exception as e:
                                logger.error(f"Error parsing fields string: {e}")
                        
                        # Ensure each field is a dict if they're strings
                        if isinstance(object_info['fields'], list):
                            fixed_fields = []
                            for i, field in enumerate(object_info['fields']):
                                if isinstance(field, str):
                                    logger.warning(f"Field at index {i} is a string, attempting to fix")
                                    try:
                                        # Try to parse as JSON
                                        parsed_field = json.loads(field)
                                        if isinstance(parsed_field, dict):
                                            logger.info(f"Successfully converted field string to dict at index {i}")
                                            fixed_fields.append(parsed_field)
                                        else:
                                            logger.warning(f"Parsed field is not a dict: {type(parsed_field)}")
                                            # Skip this field
                                    except Exception as e:
                                        logger.error(f"Error parsing field string at index {i}: {e}")
                                        # Skip this field
                                else:
                                    fixed_fields.append(field)
                            
                            object_info['fields'] = fixed_fields
                    
                    logger.debug(f"Starting intelligent data generation for {object_name}")
                    
                    # Try the new intelligent data generator first
                    try:
                        from intelligent_data_gen import IntelligentDataGenerator
                        
                        # Create a connection object to pass to the generator
                        sf_connection = type('SFConnection', (), {
                            'access_token': sf_org.access_token,
                            'instance_url': sf_org.instance_url
                        })
                        
                        # Initialize the intelligent generator
                        generator = IntelligentDataGenerator(sf_connection)
                        
                        # Generate data with the intelligent approach
                        logger.info(f"Using intelligent data generator for {object_name}")
                        result = generator.generate_data(object_name, int(record_count))
                        
                        # Check if generation was successful
                        if result["success_count"] > 0:
                            generated_data = result["records"]
                            logger.debug(f"Successfully generated {len(generated_data)} records using intelligent generator")
                        else:
                            # If intelligent generation failed, log the errors and fall back
                            error_msg = '; '.join(result['errors']) if result['errors'] else "Unknown error"
                            logger.warning(f"Intelligent data generation failed: {error_msg}")
                            
                            # Fall back to basic Faker
                            logger.debug(f"Falling back to basic Faker data generation")
                            generated_data = generate_test_data_with_faker(object_info, record_count)
                    except Exception as e:
                        # If intelligent generation fails for any reason, fall back to basic Faker
                        logger.error(f"Error using intelligent data generator: {str(e)}")
                        logger.debug(f"Falling back to basic Faker data generation")
                        generated_data = generate_test_data_with_faker(object_info, record_count)
                    
                    # Validate the generated data
                    if not generated_data:
                        logger.error(f"Failed to generate data for {object_name}")
                        raise Exception(f"Failed to generate data for {object_name}")
                        
                    logger.debug(f"Successfully generated {len(generated_data)} records")
                    
                    # Store the raw generated data before attempting to insert into Salesforce
                    job.raw_data = json.dumps(generated_data)
                    db.session.commit()
                    
                except Exception as e:
                    logger.error(f"Error in data generation: {str(e)}")
                    job.status = 'failed'
                    job.error_message = f"Data generation error: {str(e)}"
                    job.completed_at = datetime.utcnow()
                    db.session.commit()
                    flash(f'Error generating data: {str(e)}', 'danger')
                    return redirect(url_for('combined'))
                    
                
                # Insert records to Salesforce - try REST API first, then SOAP as fallback
                try:
                    if not generated_data:
                        raise Exception("No generated data to insert")
                        
                    logger.debug(f"Attempting to insert {len(generated_data)} records via REST API")
                    results = insert_records(sf_org.instance_url, sf_org.access_token, object_name, generated_data)
                    logger.debug(f"Successfully inserted {len(generated_data)} records via REST API")
                    
                except Exception as rest_error:
                    logger.warning(f"REST API failed for record insertion, falling back to SOAP: {str(rest_error)}")
                    try:
                        if not generated_data:
                            raise Exception("No generated data to insert")
                            
                        results = insert_records_soap(sf_org.instance_url, sf_org.access_token, object_name, generated_data)
                        logger.debug(f"Successfully inserted {len(generated_data)} records via SOAP API")
                    except Exception as soap_error:
                        logger.error(f"Both REST and SOAP APIs failed for record insertion: {str(soap_error)}")
                        job.status = 'failed'
                        job.error_message = f"Record insertion error: REST API: {str(rest_error)}, SOAP API: {str(soap_error)}"
                        job.completed_at = datetime.utcnow()
                        db.session.commit()
                        flash(f'Error inserting records: {str(soap_error)}', 'danger')
                        return redirect(url_for('combined'))
                
                # Update job with results
                job.status = 'completed'
                job.results = json.dumps(results)
                job.completed_at = datetime.utcnow()
                db.session.commit()
                
                flash(f'Successfully generated and inserted {record_count} records for {object_name}', 'success')
                
                # Return to the combined view with results
                sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
                objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                
                # Apply server-side search filter if search query exists
                if search_query:
                    objects = [obj for obj in objects if search_query.lower() in obj.get('label', '').lower()]
                
                org_info = get_org_info()
                return render_template('generate_with_schema.html', objects=objects, job=job, 
                                      results=results, object_name=object_name, org_info=org_info, 
                                      search_query=search_query)
                
            except Exception as e:
                logger.error(f"Error generating data: {str(e)}")
                flash(f'Error generating data: {str(e)}', 'danger')
                return redirect(url_for('combined'))
        
        # GET request - show combined interface
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Try to get objects with token refresh if needed
            try:
                objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Successfully retrieved {len(objects)} objects via REST API")
            except Exception as api_error:
                # Check if it's a 401 authorization error
                if "401" in str(api_error) or "Unauthorized" in str(api_error):
                    logger.info("Access token expired, attempting to refresh...")
                    try:
                        # Attempt to refresh the token
                        new_token_data = refresh_access_token(sf_org.refresh_token)
                        sf_org.access_token = new_token_data['access_token']
                        db.session.commit()
                        logger.info("Successfully refreshed access token")
                        
                        # Retry with new token
                        objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                        logger.debug(f"Successfully retrieved {len(objects)} objects after token refresh")
                    except Exception as refresh_error:
                        logger.error(f"Token refresh failed: {str(refresh_error)}")
                        flash('Your session has expired. Please reconnect to Salesforce.', 'warning')
                        return redirect(url_for('logout'))
                else:
                    # For other errors, try SOAP as fallback
                    logger.warning(f"REST API failed, trying SOAP fallback: {str(api_error)}")
                    objects = get_salesforce_objects_soap(sf_org.instance_url, sf_org.access_token)
                    logger.debug(f"Successfully retrieved {len(objects)} objects via SOAP API")
            
            # Apply server-side search filter if search query exists
            if search_query:
                objects = [obj for obj in objects if search_query.lower() in obj.get('label', '').lower()]
            
            org_info = get_org_info()
            return render_template('generate_with_schema.html', objects=objects,
                                  job=job, results=results, object_name=object_name, org_info=org_info, 
                                  search_query=search_query)
        except Exception as e:
            logger.error(f"Error fetching objects: {str(e)}")
            flash(f'Error retrieving Salesforce objects: {str(e)}', 'danger')
            return redirect(url_for('index'))

    @app.route('/schema-viewer')
    def schema_viewer():
        """Dedicated schema viewer page with clean search functionality"""
        if 'salesforce_org_id' not in session:
            flash('Please connect to Salesforce first', 'warning')
            return redirect(url_for('login'))
        
        try:
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            # Get Salesforce objects - try REST API first, then SOAP as fallback
            try:
                salesforce_objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Successfully retrieved {len(salesforce_objects)} objects via REST API")
            except Exception as rest_error:
                logger.warning(f"REST API failed for objects, falling back to SOAP: {str(rest_error)}")
                salesforce_objects = get_salesforce_objects_soap(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Successfully retrieved {len(salesforce_objects)} objects via SOAP API")
            
            org_info = get_org_info()
            return render_template('schema_view.html', salesforce_objects=salesforce_objects, org_info=org_info)
            
        except Exception as e:
            logger.error(f"Error fetching objects: {str(e)}")
            flash(f'Error retrieving Salesforce objects: {str(e)}', 'danger')
            return redirect(url_for('index'))

    @app.route('/generate', methods=['GET', 'POST'])
    def generate():
        """Redirect to combined page - generate functionality now only in combined view"""
        flash('The Generate Data page has been merged with the Schema & Data Gen page', 'info')
        return redirect(url_for('combined'))
        
    @app.route('/select-object')
    def select_object():
        """Simple object selector page with dedicated search"""
        # Redirect to basic selector
        return redirect(url_for('basic_selector'))
            
    @app.route('/simple-selector')
    def simple_selector():
        """Simple and reliable object selector page with minimal JS"""
        # Redirect to basic selector
        return redirect(url_for('basic_selector'))
            
    @app.route('/basic-selector')
    def basic_selector():
        """Extremely basic object selector with no fancy JS"""
        # Check if logged in
        if 'salesforce_org_id' not in session:
            flash('Please log in to Salesforce first', 'warning')
            return redirect(url_for('login'))
            
        try:
            # Get the org
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            if not sf_org:
                flash('Salesforce connection not found', 'danger')
                return redirect(url_for('login'))
                
            # Get objects
            objects = []
            
            # Try REST API first
            try:
                objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                logger.debug(f"Retrieved {len(objects)} objects via REST API")
            except Exception as e:
                logger.error(f"Error fetching objects via REST API: {e}")
                
                # Fall back to SOAP API
                try:
                    objects = get_salesforce_objects_soap(sf_org.instance_url, sf_org.access_token)
                    logger.debug(f"Retrieved {len(objects)} objects via SOAP API")
                except Exception as e2:
                    logger.error(f"Error fetching objects via SOAP API: {e2}")
                    flash(f"Could not retrieve Salesforce objects: {e2}", 'danger')
            
            return render_template('basic_selector.html', objects=objects, org_info=get_org_info())
        except Exception as e:
            logger.error(f"Error in basic_selector: {str(e)}")
            flash(f'Error retrieving Salesforce objects: {str(e)}', 'danger')
            return redirect(url_for('index'))
    
    @app.route('/configure', methods=['GET', 'POST'])
    def configure():
        """Configure Salesforce with natural language prompts"""
        # Check if the user is logged in
        is_logged_in = 'salesforce_org_id' in session
        logger.debug(f"Configure page access - logged in: {is_logged_in}")
        
        # Configuration now uses rule-based analysis with Faker (no OpenAI dependency)
        has_openai_key = True  # Always available now since we use Faker
        
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
                try:
                    objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
                    logger.debug(f"Successfully retrieved {len(objects)} objects via REST API")
                except Exception as rest_error:
                    logger.warning(f"REST API failed for objects, falling back to SOAP: {str(rest_error)}")
                    try:
                        objects = get_salesforce_objects_soap(sf_org.instance_url, sf_org.access_token)
                        logger.debug(f"Successfully retrieved {len(objects)} objects via SOAP API")
                    except Exception as soap_error:
                        logger.error(f"Both REST and SOAP APIs failed for objects: {str(soap_error)}")
                        # Continue with empty objects list - configuration can still work
                        objects = []
                
                # Simplified org info for context
                org_info = {
                    'objects': objects
                }
                
                # Analyze prompt to determine configuration
                logger.info(f"Analyzing prompt: '{prompt}' with {len(objects)} objects in org context")
                config = analyze_prompt_for_configuration(prompt, org_info)
                logger.info(f"Configuration analysis completed: {len(config.get('actions', []))} actions found")
                
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
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Error configuring Salesforce: {str(e)}")
                logger.error(f"Full traceback: {error_details}")
                flash(f'Error configuring Salesforce: {str(e)}', 'danger')
                return render_template('configure.html', prompt=prompt, results={
                    'success': False,
                    'message': str(e),
                    'details': {'error': str(e), 'traceback': error_details}
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
            org_info = get_org_info()
            return render_template('configure.html', results={
                'success': False,
                'message': str(e),
                'details': {'error': str(e)}
            }, is_logged_in=is_logged_in, has_openai_key=has_openai_key, org_info=org_info)
    
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
                
            try:
                config = json.loads(config_json)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in configuration: {str(e)}")
                flash(f'Invalid configuration format: {str(e)}', 'danger')
                return redirect(url_for('configure'))
            
            # Apply the configuration using new Metadata API approach
            try:
                # Create Salesforce connection for SOAP metadata operations
                sf_connection = None
                try:
                    from simple_salesforce import Salesforce
                    
                    # Extract domain from instance URL for proper connection
                    instance_domain = sf_org.instance_url.replace('https://', '').replace('http://', '')
                    
                    # Create connection using session ID with proper domain
                    sf_connection = Salesforce(
                        instance=instance_domain,
                        session_id=sf_org.access_token,
                        version='58.0'
                    )
                    
                    # Test the connection by making a simple API call
                    try:
                        sf_connection.describe()
                        logger.info("✓ Successfully created and tested simple-salesforce connection")
                    except Exception as test_error:
                        logger.warning(f"Connection created but test failed: {str(test_error)}")
                        sf_connection = None
                        
                except Exception as e:
                    logger.warning(f"Could not create simple-salesforce connection: {str(e)}")
                    sf_connection = None
                
                # Create metadata client for programmatic object creation
                metadata_client = create_metadata_client(sf_org.instance_url, sf_org.access_token, sf_connection)
                result = metadata_client.apply_configuration(config)
                
                logger.info(f"Metadata API configuration result: {result}")
                
            except Exception as metadata_error:
                logger.warning(f"Metadata API failed, falling back to old method: {str(metadata_error)}")
                # Fallback to original configuration method
                result = apply_configuration(sf_org.instance_url, sf_org.access_token, config)
            
            if 'success' in result and result['success']:
                flash('Configuration applied successfully', 'success')
            else:
                flash(f'Error applying configuration: {result["message"] if "message" in result else "Unknown error"}', 'danger')
                
            # Return to configure page with the result
            org_info = get_org_info()
            return render_template('configure.html', results={
                'success': result['success'] if 'success' in result else False,
                'message': result['message'] if 'message' in result else 'Configuration applied.',
                'details': result
            }, is_logged_in=True, has_openai_key=bool(app.config.get('OPENAI_API_KEY')), org_info=org_info)
            
        except Exception as e:
            logger.error(f"Error applying configuration: {str(e)}")
            flash(f'Error applying configuration: {str(e)}', 'danger')
            return redirect(url_for('configure'))
    
    @app.route('/test-config', methods=['POST'])
    def test_config():
        """Test configuration generation without requiring Salesforce authentication"""
        try:
            prompt = request.form.get('prompt', 'Create the custom objects called Project, projections, prompting, proper')
            
            # Test the parser without authentication
            config = analyze_prompt_for_configuration(prompt, [])
            
            return jsonify({
                'success': True,
                'message': f'Configuration parsed successfully: found {len(config.get("actions", []))} actions',
                'config': config
            })
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Error testing configuration: {str(e)}")
            logger.error(f"Full traceback: {error_details}")
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': error_details
            }), 500
            
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
            
    @app.route('/api/export/csv/<int:job_id>', methods=['GET'])
    def export_csv(job_id):
        """Export generated data to CSV format with enhanced functionality"""
        if 'salesforce_org_id' not in session:
            return jsonify({'error': 'Not connected to Salesforce'}), 401
            
        try:
            # Retrieve the job from the database
            job = GenerationJob.query.get_or_404(job_id)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{job.object_name}_data_{timestamp}.csv"
            
            # Get the object details to use field labels as column headers
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            try:
                # Attempt to get object metadata via REST API
                object_info = get_object_describe(sf_org.instance_url, sf_org.access_token, job.object_name)
                logger.debug(f"Successfully retrieved object details for {job.object_name} via REST API")
            except Exception as rest_error:
                # Fall back to SOAP API if REST fails
                logger.warning(f"REST API failed for object detail, falling back to SOAP: {str(rest_error)}")
                try:
                    from salesforce_soap_utils import get_object_describe_soap
                    object_info = get_object_describe_soap(sf_org.instance_url, sf_org.access_token, job.object_name)
                    logger.debug(f"Successfully retrieved object details for {job.object_name} via SOAP API")
                except Exception as soap_error:
                    logger.error(f"Both REST and SOAP APIs failed: {str(soap_error)}")
                    object_info = {'fields': []}  # Empty fallback
            
            # Build a mapping of field names to field labels for better CSV headers
            field_label_map = {}
            field_type_map = {}
            
            try:
                for field in object_info.get('fields', []):
                    field_name = field.get('name')
                    field_label = field.get('label')
                    field_type = field.get('type')
                    
                    if field_name and field_label:
                        field_label_map[field_name] = field_label
                    
                    if field_name and field_type:
                        field_type_map[field_name] = field_type
            except Exception as e:
                logger.warning(f"Error processing field metadata: {str(e)}")
            
            # Extract records from the job with comprehensive data source checking
            records = []
            
            # Function to extract records from various data formats
            def extract_records_from_data(data):
                if not data:
                    return []
                    
                extracted = []
                
                # Handle different data structures
                if isinstance(data, dict):
                    # Composite API response format
                    if 'compositeResponse' in data:
                        composite_records = []
                        for response in data.get('compositeResponse', []):
                            if response.get('httpStatusCode') in [200, 201]:
                                body = response.get('body', {})
                                if isinstance(body, dict):
                                    composite_records.append(body)
                                elif isinstance(body, list):
                                    composite_records.extend(body)
                        extracted.extend(composite_records)
                    
                    # Standard query results format
                    elif 'records' in data:
                        extracted.extend(data.get('records', []))
                    
                    # Direct data in 'generated_data' key
                    elif 'generated_data' in data:
                        gen_data = data.get('generated_data')
                        if isinstance(gen_data, list):
                            extracted.extend(gen_data)
                
                # Direct list of records
                elif isinstance(data, list):
                    extracted.extend(data)
                
                return extracted
            
            # Try all possible data sources in priority order
            data_sources = []
            
            # 1. Try the raw_data field first (most complete pre-insertion data)
            if hasattr(job, 'raw_data') and job.raw_data:
                try:
                    raw_data = json.loads(job.raw_data)
                    data_sources.append(('raw_data', raw_data))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Could not parse raw_data as JSON: {str(e)}")
            
            # 2. Then try the results field (post-insertion data)
            if job.results:
                try:
                    results_data = json.loads(job.results)
                    data_sources.append(('results', results_data))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Could not parse results as JSON: {str(e)}")
            
            # Extract records from all data sources
            for source_name, source_data in data_sources:
                extracted_records = extract_records_from_data(source_data)
                if extracted_records:
                    records = extracted_records
                    logger.debug(f"Found {len(records)} records in {source_name}")
                    break
            
            # If we still have no records after trying all sources
            if not records:
                flash('No data records available for export', 'warning')
                return redirect(url_for('combined'))
            
            # Determine fields to include in the CSV
            # Start with fields from the first record
            if records and isinstance(records[0], dict):
                field_names = list(records[0].keys())
                
                # Add any missing fields from other records (to handle inconsistent record structures)
                for record in records[1:]:
                    if isinstance(record, dict):
                        for key in record.keys():
                            if key not in field_names:
                                field_names.append(key)
            else:
                # Fallback to fields from object metadata
                field_names = [field.get('name') for field in object_info.get('fields', []) 
                              if field.get('name') not in ['Id', 'OwnerId']]
            
            # Create a CSV in memory with improved formatting
            output = io.StringIO()
            
            # Use field labels as headers if available, otherwise use field names
            csv_headers = []
            for field_name in field_names:
                # Use label if available, otherwise use the field name
                header = field_label_map.get(field_name, field_name)
                csv_headers.append(header)
            
            writer = csv.writer(output)
            # Write the headers
            writer.writerow(csv_headers)
            
            # Format and write each record
            for record in records:
                if not isinstance(record, dict):
                    continue
                    
                row = []
                for field_name in field_names:
                    value = record.get(field_name)
                    
                    # Format values appropriately based on field type
                    if value is not None:
                        # Format boolean values as "Yes"/"No"
                        if field_type_map.get(field_name) == 'boolean':
                            value = "Yes" if value else "No"
                        # Format date/datetime values nicely
                        elif field_type_map.get(field_name) in ['date', 'datetime'] and isinstance(value, str):
                            try:
                                if 'T' in value:  # ISO datetime format
                                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                    value = dt.strftime('%Y-%m-%d %H:%M:%S')
                                else:  # ISO date format
                                    dt = datetime.fromisoformat(value)
                                    value = dt.strftime('%Y-%m-%d')
                            except (ValueError, TypeError):
                                pass  # Keep original if parsing fails
                    
                    row.append(value)
                    
                writer.writerow(row)
            
            # Return the CSV as a file download with an improved filename
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment;filename={filename}'}
            )
                
        except Exception as e:
            logger.error(f"Error exporting CSV: {str(e)}")
            flash(f'Error exporting CSV: {str(e)}', 'danger')
            return redirect(url_for('combined'))
            
    @app.route('/api/export/json/<int:job_id>', methods=['GET'])
    def export_json(job_id):
        """Export generated data to JSON format with enhanced functionality"""
        if 'salesforce_org_id' not in session:
            return jsonify({'error': 'Not connected to Salesforce'}), 401
            
        try:
            # Retrieve the job from the database
            job = GenerationJob.query.get_or_404(job_id)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{job.object_name}_data_{timestamp}.json"
            
            # Get the object details for metadata enrichment
            sf_org = SalesforceOrg.query.get(session['salesforce_org_id'])
            
            try:
                # Attempt to get object metadata via REST API
                object_info = get_object_describe(sf_org.instance_url, sf_org.access_token, job.object_name)
                logger.debug(f"Successfully retrieved object details for {job.object_name} via REST API")
            except Exception as rest_error:
                # Fall back to SOAP API if REST fails
                logger.warning(f"REST API failed for object detail, falling back to SOAP: {str(rest_error)}")
                try:
                    from salesforce_soap_utils import get_object_describe_soap
                    object_info = get_object_describe_soap(sf_org.instance_url, sf_org.access_token, job.object_name)
                    logger.debug(f"Successfully retrieved object details for {job.object_name} via SOAP API")
                except Exception as soap_error:
                    logger.error(f"Both REST and SOAP APIs failed: {str(soap_error)}")
                    object_info = {'fields': []}  # Empty fallback
            # Function to extract records from various data formats
            def extract_records_from_data(data):
                if not data:
                    return []
                    
                extracted = []
                
                # Handle different data structures
                if isinstance(data, dict):
                    # Composite API response format
                    if 'compositeResponse' in data:
                        composite_records = []
                        for response in data.get('compositeResponse', []):
                            if response.get('httpStatusCode') in [200, 201]:
                                body = response.get('body', {})
                                if isinstance(body, dict):
                                    composite_records.append(body)
                                elif isinstance(body, list):
                                    composite_records.extend(body)
                        extracted.extend(composite_records)
                    
                    # Standard query results format
                    elif 'records' in data:
                        extracted.extend(data.get('records', []))
                    
                    # Direct data in 'generated_data' key
                    elif 'generated_data' in data:
                        gen_data = data.get('generated_data')
                        if isinstance(gen_data, list):
                            extracted.extend(gen_data)
                
                # Direct list of records
                elif isinstance(data, list):
                    extracted.extend(data)
                
                return extracted
            
            # Try all possible data sources in priority order
            data_sources = []
            
            # 1. Try the raw_data field first (most complete pre-insertion data)
            if hasattr(job, 'raw_data') and job.raw_data:
                try:
                    raw_data = json.loads(job.raw_data)
                    data_sources.append(('raw_data', raw_data))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Could not parse raw_data as JSON: {str(e)}")
            
            # 2. Then try the results field (post-insertion data)
            if job.results:
                try:
                    results_data = json.loads(job.results)
                    data_sources.append(('results', results_data))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Could not parse results as JSON: {str(e)}")
            
            # Extract records from all data sources
            records = []
            for source_name, source_data in data_sources:
                extracted_records = extract_records_from_data(source_data)
                if extracted_records:
                    records = extracted_records
                    logger.debug(f"Found {len(records)} records in {source_name}")
                    break
            
            # If we still have no records after trying all sources
            if not records:
                flash('No data records available for export', 'warning')
                return redirect(url_for('combined'))
            
            # Enhance the JSON response with metadata
            field_info = {}
            try:
                # Process field metadata for enhancing the export
                for field in object_info.get('fields', []):
                    field_name = field.get('name')
                    if field_name:
                        field_info[field_name] = {
                            'label': field.get('label'),
                            'type': field.get('type'),
                            'description': field.get('description') or '',
                            'required': not field.get('nillable', True),
                            'createable': field.get('createable', False),
                            'updateable': field.get('updateable', False)
                        }
            except Exception as e:
                logger.warning(f"Error processing field metadata: {str(e)}")
                
            # Create enhanced JSON export data
            export_data = {
                'metadata': {
                    'object': job.object_name,
                    'objectLabel': object_info.get('label', job.object_name),
                    'generatedAt': datetime.now().isoformat(),
                    'recordCount': len(records),
                    'exportFormat': 'JSON',
                    'jobId': job.id,
                    'source': 'Salesforce GPT Data Generator'
                },
                'fieldInfo': field_info,
                'records': records
            }
            
            # Return formatted JSON for easy readability
            return Response(
                json.dumps(export_data, indent=2, default=str),  # default=str handles non-serializable types
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment;filename={filename}'}
            )
                
        except Exception as e:
            logger.error(f"Error exporting JSON: {str(e)}")
            flash(f'Error exporting JSON: {str(e)}', 'danger')
            return redirect(url_for('combined'))
    
    @app.route('/auth-help')
    def auth_help():
        """Show authentication troubleshooting guide"""
        return render_template('auth_help.html')


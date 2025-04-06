import os
import json
import logging
from urllib.parse import urlencode
from flask import render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime, timedelta

from app import db
from models import SalesforceOrg, SchemaObject, SchemaField, GenerationJob
from salesforce_utils import (
    get_auth_url, get_access_token, refresh_access_token, 
    get_salesforce_objects, get_object_fields, 
    get_object_describe, insert_records
)
from openai_utils import generate_test_data_with_gpt

logger = logging.getLogger(__name__)

def init_routes(app):
    
    @app.route('/')
    def index():
        """Homepage with connection status and navigation"""
        sf_connected = 'salesforce_org_id' in session
        return render_template('index.html', sf_connected=sf_connected)
    
    @app.route('/login')
    def login():
        """Salesforce login page"""
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
    def salesforce_callback():
        """Handle Salesforce OAuth callback"""
        code = request.args.get('code')
        
        if not code:
            flash('Authentication failed: No authorization code received', 'danger')
            return redirect(url_for('login'))
        
        try:
            # Exchange code for token
            token_data = get_access_token(code)
            
            if not token_data or 'access_token' not in token_data:
                flash('Failed to obtain access token', 'danger')
                return redirect(url_for('login'))
            
            # Store connection in database
            sf_org = SalesforceOrg(
                instance_url=token_data.get('instance_url'),
                access_token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                org_id=token_data.get('id', '').split('/')[-2] if 'id' in token_data else None
            )
            
            db.session.add(sf_org)
            db.session.commit()
            
            # Store in session
            session['salesforce_org_id'] = sf_org.id
            session['salesforce_instance_url'] = sf_org.instance_url
            session['salesforce_access_token'] = sf_org.access_token
            
            flash('Successfully connected to Salesforce', 'success')
            return redirect(url_for('schema'))
            
        except Exception as e:
            logger.error(f"Error during Salesforce callback: {str(e)}")
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
            
            # Get objects from Salesforce
            objects = get_salesforce_objects(sf_org.instance_url, sf_org.access_token)
            
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
            
            # Get object describe info
            object_info = get_object_describe(sf_org.instance_url, sf_org.access_token, object_name)
            
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
                
                # Get object describe info
                object_info = get_object_describe(sf_org.instance_url, sf_org.access_token, object_name)
                
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
                
                # Insert records to Salesforce
                results = insert_records(sf_org.instance_url, sf_org.access_token, object_name, generated_data)
                
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

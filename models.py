from app import db
from datetime import datetime

class SalesforceOrg(db.Model):
    """Model to store Salesforce org connection details"""
    id = db.Column(db.Integer, primary_key=True)
    instance_url = db.Column(db.String(255), nullable=False)
    access_token = db.Column(db.String(255), nullable=False)
    refresh_token = db.Column(db.String(255), nullable=True)
    org_id = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SalesforceOrg {self.org_id}>'

class SchemaObject(db.Model):
    """Model to store Salesforce schema object metadata"""
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.String(50), nullable=False)
    object_name = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(255))
    api_name = db.Column(db.String(255), nullable=False)
    is_custom = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SchemaObject {self.api_name}>'

class SchemaField(db.Model):
    """Model to store Salesforce schema field metadata"""
    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(db.Integer, db.ForeignKey('schema_object.id'), nullable=False)
    field_name = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(255))
    api_name = db.Column(db.String(255), nullable=False)
    data_type = db.Column(db.String(50))
    is_required = db.Column(db.Boolean, default=False)
    is_unique = db.Column(db.Boolean, default=False)
    is_custom = db.Column(db.Boolean, default=False)
    relationship_name = db.Column(db.String(255))
    reference_to = db.Column(db.String(255))
    picklist_values = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to parent object
    object = db.relationship('SchemaObject', backref='fields')
    
    def __repr__(self):
        return f'<SchemaField {self.api_name}>'

class GenerationJob(db.Model):
    """Model to track data generation jobs"""
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.String(50), nullable=False)
    object_name = db.Column(db.String(255), nullable=False)
    record_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='pending')
    error_message = db.Column(db.Text)
    results = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<GenerationJob {self.id} - {self.object_name}>'

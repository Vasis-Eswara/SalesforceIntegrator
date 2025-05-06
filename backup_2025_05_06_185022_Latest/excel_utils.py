"""
Utilities for generating and processing Excel configuration templates
"""
import os
import pandas as pd
import logging

# Set up logging
logger = logging.getLogger(__name__)

def generate_object_template():
    """
    Generate an Excel template for custom object configuration
    """
    try:
        # Create a DataFrame for the custom object sheet
        object_df = pd.DataFrame({
            'Object Label': ['Customer', 'Project'],
            'Object API Name': ['Customer__c', 'Project__c'],
            'Description': ['Custom object for customer information', 'Custom object for project management'],
            'Enable Reports': ['Yes', 'Yes'],
            'Enable Activities': ['Yes', 'No'],
            'Track Field History': ['Yes', 'Yes'],
            'Deployment Status': ['Deployed', 'Deployed'],
            'Allow Sharing': ['Yes', 'Yes'],
            'Allow Bulk API Access': ['Yes', 'Yes'],
            'Allow Streaming API Access': ['Yes', 'Yes'],
            'Notes': ['Example object - replace with your data', 'Example object - replace with your data']
        })
        
        # Create a DataFrame for the field sheet
        field_df = pd.DataFrame({
            'Object API Name': ['Customer__c', 'Customer__c', 'Project__c', 'Project__c', 'Project__c'],
            'Field Label': ['Customer Name', 'Industry', 'Project Name', 'Start Date', 'Budget'],
            'Field API Name': ['Name', 'Industry__c', 'Name', 'Start_Date__c', 'Budget__c'],
            'Data Type': ['Text', 'Picklist', 'Text', 'Date', 'Currency'],
            'Length': [80, None, 80, None, None],
            'Decimal Places': [None, None, None, None, 2],
            'Required': ['Yes', 'No', 'Yes', 'Yes', 'No'],
            'Unique': ['Yes', 'No', 'Yes', 'No', 'No'],
            'External ID': ['No', 'No', 'No', 'No', 'No'],
            'Default Value': [None, None, None, 'TODAY()', None],
            'Formula': [None, None, None, None, None],
            'Picklist Values': [None, 'Technology;Finance;Healthcare;Education;Retail;Other', None, None, None],
            'Description': ['Customer name', 'Industry type', 'Project name', 'Project start date', 'Project budget'],
            'Help Text': ['Enter customer name', 'Select the industry', 'Enter project name', 'Select start date', 'Enter budget amount'],
            'Notes': ['Example field - replace with your data'] * 5
        })
        
        # Create a DataFrame for the validation rules sheet
        validation_df = pd.DataFrame({
            'Object API Name': ['Project__c'],
            'Rule Name': ['Budget_Check'],
            'Active': ['Yes'],
            'Error Condition Formula': ['Budget__c < 1000'],
            'Error Message': ['Budget must be at least $1,000'],
            'Error Location': ['Budget__c'],
            'Notes': ['Example validation rule - replace with your data']
        })
        
        # Create an Excel writer
        template_path = os.path.join('static', 'templates', 'salesforce_configuration_template.xlsx')
        
        # Create a Pandas Excel writer using XlsxWriter as the engine
        writer = pd.ExcelWriter(template_path, engine='openpyxl')
        
        # Write each DataFrame to a different worksheet
        object_df.to_excel(writer, sheet_name='Custom Objects', index=False)
        field_df.to_excel(writer, sheet_name='Custom Fields', index=False)
        validation_df.to_excel(writer, sheet_name='Validation Rules', index=False)
        
        # Add a README sheet with instructions
        instructions = pd.DataFrame({
            'Instructions': [
                'This template is used to define Salesforce configuration changes.',
                'Fill out the appropriate sheets based on your needs:',
                '1. Custom Objects - Define new custom objects',
                '2. Custom Fields - Define fields for standard or custom objects',
                '3. Validation Rules - Define validation rules for objects',
                '',
                'Guidelines:',
                '- Object API Name must end with __c for custom objects',
                '- Field API Name must end with __c for custom fields',
                '- Data Types: Text, Number, Date, DateTime, Checkbox, Currency, Percent, Phone, Email, URL, Picklist, TextArea, LongTextArea, Html, EncryptedText, Lookup, MasterDetail',
                '- For picklists, separate values with semicolons in the Picklist Values column',
                '- For lookup/master-detail fields, specify the referenced object in the Formula column'
            ]
        })
        instructions.to_excel(writer, sheet_name='README', index=False)
        
        # Save the Excel file
        writer.close()
        
        logger.info(f"Excel template generated successfully at {template_path}")
        return template_path
        
    except Exception as e:
        logger.error(f"Error generating Excel template: {str(e)}")
        raise

def process_excel_configuration(file_path):
    """
    Process an uploaded Excel configuration file
    
    Args:
        file_path (str): Path to the uploaded Excel file
        
    Returns:
        dict: Configuration to apply
    """
    try:
        # Read the Excel file
        objects_df = pd.read_excel(file_path, sheet_name='Custom Objects')
        fields_df = pd.read_excel(file_path, sheet_name='Custom Fields')
        validations_df = pd.read_excel(file_path, sheet_name='Validation Rules', engine='openpyxl')
        
        # Process custom objects
        objects = []
        for index, row in objects_df.iterrows():
            # Skip example rows
            if 'example' in str(row['Notes']).lower():
                continue
                
            obj = {
                'label': row['Object Label'],
                'apiName': row['Object API Name'],
                'description': row['Description'],
                'enableReports': row['Enable Reports'] == 'Yes',
                'enableActivities': row['Enable Activities'] == 'Yes',
                'trackFieldHistory': row['Track Field History'] == 'Yes',
                'deploymentStatus': row['Deployment Status'],
                'sharingModel': 'ReadWrite' if row['Allow Sharing'] == 'Yes' else 'Private',
                'allowBulkApi': row['Allow Bulk API Access'] == 'Yes',
                'allowStreamingApi': row['Allow Streaming API Access'] == 'Yes'
            }
            objects.append(obj)
        
        # Process custom fields
        fields = []
        for index, row in fields_df.iterrows():
            # Skip example rows
            if 'example' in str(row['Notes']).lower():
                continue
                
            field = {
                'objectName': row['Object API Name'],
                'label': row['Field Label'],
                'apiName': row['Field API Name'],
                'type': row['Data Type'],
                'length': row['Length'] if not pd.isna(row['Length']) else None,
                'precision': row['Decimal Places'] if not pd.isna(row['Decimal Places']) else None,
                'required': row['Required'] == 'Yes',
                'unique': row['Unique'] == 'Yes',
                'externalId': row['External ID'] == 'Yes',
                'defaultValue': row['Default Value'] if not pd.isna(row['Default Value']) else None,
                'formula': row['Formula'] if not pd.isna(row['Formula']) else None,
                'picklistValues': row['Picklist Values'].split(';') if not pd.isna(row['Picklist Values']) else None,
                'description': row['Description'],
                'helpText': row['Help Text']
            }
            fields.append(field)
        
        # Process validation rules
        validation_rules = []
        for index, row in validations_df.iterrows():
            # Skip example rows
            if 'example' in str(row['Notes']).lower():
                continue
                
            rule = {
                'objectName': row['Object API Name'],
                'ruleName': row['Rule Name'],
                'active': row['Active'] == 'Yes',
                'errorConditionFormula': row['Error Condition Formula'],
                'errorMessage': row['Error Message'],
                'errorLocation': row['Error Location']
            }
            validation_rules.append(rule)
        
        # Create final configuration
        config = {
            'objects': objects,
            'fields': fields,
            'validationRules': validation_rules
        }
        
        return config
        
    except Exception as e:
        logger.error(f"Error processing Excel configuration: {str(e)}")
        raise
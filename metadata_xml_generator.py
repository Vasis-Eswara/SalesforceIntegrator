"""
Programmatic XML metadata generation for Salesforce custom objects
Creates proper metadata XML that can be deployed via SOAP Metadata API
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import tempfile
import zipfile
import base64

class MetadataXMLGenerator:
    """Generate Salesforce metadata XML for custom objects and fields"""
    
    def __init__(self):
        self.namespace = "http://soap.sforce.com/2006/04/metadata"
        
    def generate_custom_object_xml(self, object_config):
        """
        Generate custom object XML metadata
        
        Args:
            object_config (dict): Object configuration
            
        Returns:
            str: XML metadata as string
        """
        # Create root element with namespace
        root = ET.Element("CustomObject", xmlns=self.namespace)
        
        # Basic object properties
        ET.SubElement(root, "label").text = object_config.get('label', 'Custom Object')
        ET.SubElement(root, "pluralLabel").text = object_config.get('pluralLabel', 'Custom Objects')
        
        # Name field (required)
        name_field = ET.SubElement(root, "nameField")
        ET.SubElement(name_field, "label").text = "Name"
        ET.SubElement(name_field, "type").text = "Text"
        
        # Deployment status
        ET.SubElement(root, "deploymentStatus").text = "Deployed"
        
        # Sharing model
        ET.SubElement(root, "sharingModel").text = "ReadWrite"
        
        # Features
        ET.SubElement(root, "enableActivities").text = "true"
        ET.SubElement(root, "enableReports").text = "true"
        ET.SubElement(root, "enableSearch").text = "true"
        ET.SubElement(root, "enableHistory").text = "false"
        ET.SubElement(root, "enableFeeds").text = "false"
        ET.SubElement(root, "enableBulkApi").text = "true"
        ET.SubElement(root, "enableStreamingApi").text = "true"
        
        # Description
        if object_config.get('description'):
            ET.SubElement(root, "description").text = object_config['description']
            
        # Convert to formatted XML string
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="    ")
    
    def generate_custom_field_xml(self, field_config):
        """
        Generate custom field XML metadata
        
        Args:
            field_config (dict): Field configuration
            
        Returns:
            str: XML metadata as string
        """
        root = ET.Element("CustomField", xmlns=self.namespace)
        
        # Basic field properties
        ET.SubElement(root, "fullName").text = field_config.get('fullName', 'Custom_Field__c')
        ET.SubElement(root, "label").text = field_config.get('label', 'Custom Field')
        ET.SubElement(root, "type").text = field_config.get('type', 'Text')
        
        # Type-specific properties
        field_type = field_config.get('type', 'Text')
        
        if field_type == 'Text':
            ET.SubElement(root, "length").text = str(field_config.get('length', 255))
        elif field_type == 'LongTextArea':
            ET.SubElement(root, "length").text = str(field_config.get('length', 32768))
            ET.SubElement(root, "visibleLines").text = str(field_config.get('visibleLines', 5))
        elif field_type == 'Number':
            ET.SubElement(root, "precision").text = str(field_config.get('precision', 18))
            ET.SubElement(root, "scale").text = str(field_config.get('scale', 0))
        elif field_type == 'Currency':
            ET.SubElement(root, "precision").text = str(field_config.get('precision', 18))
            ET.SubElement(root, "scale").text = str(field_config.get('scale', 2))
        elif field_type == 'Picklist':
            # Add picklist values
            value_set = ET.SubElement(root, "valueSet")
            ET.SubElement(value_set, "restricted").text = "true"
            for value in field_config.get('picklistValues', []):
                value_elem = ET.SubElement(value_set, "valueSetDefinition")
                val = ET.SubElement(value_elem, "value")
                ET.SubElement(val, "fullName").text = value
                ET.SubElement(val, "default").text = "false"
                ET.SubElement(val, "label").text = value
        
        # Common properties
        ET.SubElement(root, "required").text = str(field_config.get('required', False)).lower()
        ET.SubElement(root, "unique").text = str(field_config.get('unique', False)).lower()
        ET.SubElement(root, "externalId").text = str(field_config.get('externalId', False)).lower()
        
        if field_config.get('description'):
            ET.SubElement(root, "description").text = field_config['description']
            
        # Convert to formatted XML string
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="    ")
    
    def create_metadata_package(self, object_name, object_xml, fields_xml=None):
        """
        Create a metadata package (zip file) for deployment
        
        Args:
            object_name (str): Name of the custom object
            object_xml (str): Custom object XML
            fields_xml (list): List of field XML strings
            
        Returns:
            str: Base64 encoded zip file content
        """
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create package.xml
            package_xml = self._generate_package_xml(object_name, fields_xml)
            
            # Create objects directory
            objects_dir = os.path.join(temp_dir, 'objects')
            os.makedirs(objects_dir)
            
            # Write object XML
            object_file = os.path.join(objects_dir, f"{object_name}.object")
            with open(object_file, 'w') as f:
                f.write(object_xml)
            
            # Write fields XML if provided
            if fields_xml:
                for field_name, field_xml in fields_xml.items():
                    field_file = os.path.join(objects_dir, f"{object_name}.{field_name}.field")
                    with open(field_file, 'w') as f:
                        f.write(field_xml)
            
            # Write package.xml
            package_file = os.path.join(temp_dir, 'package.xml')
            with open(package_file, 'w') as f:
                f.write(package_xml)
            
            # Create zip file
            zip_path = os.path.join(temp_dir, 'metadata.zip')
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add package.xml
                zipf.write(package_file, 'package.xml')
                
                # Add object file
                zipf.write(object_file, f'objects/{object_name}.object')
                
                # Add field files
                if fields_xml:
                    for field_name in fields_xml.keys():
                        field_file = os.path.join(objects_dir, f"{object_name}.{field_name}.field")
                        zipf.write(field_file, f'objects/{object_name}.{field_name}.field')
            
            # Read and encode zip file
            with open(zip_path, 'rb') as f:
                zip_content = f.read()
                
            return base64.b64encode(zip_content).decode('utf-8')
    
    def _generate_package_xml(self, object_name, fields_xml):
        """Generate package.xml for metadata deployment"""
        root = ET.Element("Package", xmlns=self.namespace)
        
        # API version
        ET.SubElement(root, "version").text = "58.0"
        
        # Custom object type
        types = ET.SubElement(root, "types")
        ET.SubElement(types, "name").text = "CustomObject"
        ET.SubElement(types, "members").text = object_name
        
        # Custom field type (if fields provided)
        if fields_xml:
            field_types = ET.SubElement(root, "types")
            ET.SubElement(field_types, "name").text = "CustomField"
            for field_name in fields_xml.keys():
                ET.SubElement(field_types, "members").text = f"{object_name}.{field_name}"
        
        # Convert to formatted XML string
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="    ")

def create_metadata_generator():
    """Factory function to create metadata generator"""
    return MetadataXMLGenerator()
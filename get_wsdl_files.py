#!/usr/bin/env python3
"""
Script to download WSDL files from Salesforce org
Run this after connecting to your org to get the required WSDL files
"""

import requests
import os
from salesforce_utils import get_salesforce_connection

def download_wsdl_files():
    """
    Download Partner and Metadata WSDL files from Salesforce
    """
    try:
        # Get Salesforce connection
        sf = get_salesforce_connection()
        if not sf:
            print("❌ No Salesforce connection found. Please connect to your org first.")
            return False
        
        instance_url = sf.sf.base_url.replace('/services/data/', '')
        session_id = sf.sf.session_id
        
        # WSDL URLs
        partner_wsdl_url = f"{instance_url}/services/wsdl/partner"
        metadata_wsdl_url = f"{instance_url}/services/wsdl/metadata"
        
        headers = {
            'Authorization': f'Bearer {session_id}',
            'Content-Type': 'application/xml'
        }
        
        print(f"📡 Downloading WSDL files from: {instance_url}")
        
        # Download Partner WSDL
        print("⬇️  Downloading Partner WSDL...")
        partner_response = requests.get(partner_wsdl_url, headers=headers)
        if partner_response.status_code == 200:
            with open('partner.wsdl.xml', 'w') as f:
                f.write(partner_response.text)
            print("✅ Partner WSDL saved as partner.wsdl.xml")
        else:
            print(f"❌ Failed to download Partner WSDL: {partner_response.status_code}")
        
        # Download Metadata WSDL
        print("⬇️  Downloading Metadata WSDL...")
        metadata_response = requests.get(metadata_wsdl_url, headers=headers)
        if metadata_response.status_code == 200:
            with open('metadata.wsdl.xml', 'w') as f:
                f.write(metadata_response.text)
            print("✅ Metadata WSDL saved as metadata.wsdl.xml")
        else:
            print(f"❌ Failed to download Metadata WSDL: {metadata_response.status_code}")
        
        print("\n🎉 WSDL files downloaded successfully!")
        print("You can now use the enhanced SOAP Metadata API functionality.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error downloading WSDL files: {str(e)}")
        return False

if __name__ == "__main__":
    download_wsdl_files()
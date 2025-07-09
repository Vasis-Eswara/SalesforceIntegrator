#!/usr/bin/env python3
"""
Direct WSDL file download using authenticated session
"""
import os
import sys
import requests
from flask import Flask
from app import app

def download_wsdl_files():
    """Download WSDL files using session from Flask app"""
    try:
        with app.app_context():
            # Get session data
            from flask import session
            
            # Check if we have an authenticated session
            if 'access_token' not in session:
                print("❌ No authenticated session found")
                print("Please connect to Salesforce first via the web interface")
                return False
                
            access_token = session['access_token']
            instance_url = session.get('instance_url', 'https://smartcart-dev-ed.develop.my.salesforce.com')
            
            # Clean instance URL
            if instance_url.endswith('/'):
                instance_url = instance_url[:-1]
            
            print(f"📡 Downloading WSDL files from: {instance_url}")
            print(f"🔑 Using access token: {access_token[:20]}...")
            
            # Headers for authenticated requests
            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': 'SalesforceWSDLDownloader/1.0'
            }
            
            # Download Metadata WSDL
            metadata_url = f"{instance_url}/services/wsdl/metadata"
            print(f"⬇️  Downloading Metadata WSDL from: {metadata_url}")
            
            response = requests.get(metadata_url, headers=headers, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                if content.startswith('<?xml') and 'wsdl' in content.lower():
                    with open('metadata.wsdl.xml', 'w') as f:
                        f.write(content)
                    print("✅ Metadata WSDL saved successfully")
                else:
                    print("❌ Metadata WSDL contains invalid content")
                    print(f"Content preview: {content[:200]}...")
                    return False
            else:
                print(f"❌ Failed to download Metadata WSDL: {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return False
            
            # Download Partner WSDL
            partner_url = f"{instance_url}/services/wsdl/partner"
            print(f"⬇️  Downloading Partner WSDL from: {partner_url}")
            
            response = requests.get(partner_url, headers=headers, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                if content.startswith('<?xml') and 'wsdl' in content.lower():
                    with open('partner.wsdl.xml', 'w') as f:
                        f.write(content)
                    print("✅ Partner WSDL saved successfully")
                else:
                    print("❌ Partner WSDL contains invalid content")
                    print(f"Content preview: {content[:200]}...")
                    return False
            else:
                print(f"❌ Failed to download Partner WSDL: {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return False
            
            print("\n🎉 WSDL files downloaded successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Error downloading WSDL files: {str(e)}")
        return False

if __name__ == "__main__":
    if download_wsdl_files():
        print("\n🔧 Testing SOAP client initialization...")
        try:
            import zeep
            client = zeep.Client('metadata.wsdl.xml')
            print("✅ SOAP client initialized successfully!")
        except Exception as e:
            print(f"❌ SOAP client test failed: {str(e)}")
    else:
        print("\n📝 Manual download instructions:")
        print("1. Log into Salesforce org")
        print("2. Go to Setup → API → Generate WSDL")
        print("3. Download 'Metadata WSDL' and 'Partner WSDL'")
        print("4. Save as 'metadata.wsdl.xml' and 'partner.wsdl.xml'")
        print("5. Upload to Replit project root")
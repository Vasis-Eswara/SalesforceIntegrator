# Manual WSDL Download Instructions

Since the automatic download may not work due to authentication requirements, here's how to manually get the WSDL files:

## Step 1: Get WSDL Files from Salesforce

1. **Log into your Salesforce org** (https://smartcart-dev-ed.develop.my.salesforce.com)

2. **Go to Setup** → **Platform Tools** → **Integration** → **API** 

3. **Generate WSDL Files**:
   - Click **"Generate Enterprise WSDL"** or **"Generate Partner WSDL"**
   - Save the file as `partner.wsdl.xml`
   - Click **"Generate Metadata WSDL"** 
   - Save the file as `metadata.wsdl.xml`

## Step 2: Upload to Replit

1. **In Replit**: Click the **"Files"** panel on the left sidebar
2. **Upload both files** to the root directory of your project:
   - `partner.wsdl.xml`
   - `metadata.wsdl.xml`

## Step 3: Verify Installation

The system will automatically detect these files and use them for enhanced SOAP API functionality.

## Alternative: Direct URLs

If you have admin access, you can also access these URLs directly:

- **Partner WSDL**: `https://your-org.salesforce.com/services/wsdl/class/YOUR_ORG_ID`
- **Metadata WSDL**: `https://your-org.salesforce.com/services/wsdl/metadata`

Replace `your-org` with your actual Salesforce domain and `YOUR_ORG_ID` with your org ID.
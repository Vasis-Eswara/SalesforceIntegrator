# Manual WSDL Download Instructions

For enhanced SOAP API functionality, you'll need to download WSDL files manually from your Salesforce org:

## Step 1: Access Salesforce Setup

1. **Log into your Salesforce org**: https://smartcart-dev-ed.develop.my.salesforce.com
2. **Go to Setup** (gear icon in top right)
3. **Navigate to**: Platform Tools → Integration → API

## Step 2: Generate WSDL Files

**For Metadata WSDL:**
1. Click **"Generate Metadata WSDL"**
2. Click **"Generate"** button
3. **Right-click** on the generated WSDL link and **"Save As"**
4. Save the file as `metadata.wsdl.xml`

**For Partner WSDL:**
1. Click **"Generate Partner WSDL"**
2. Click **"Generate"** button  
3. **Right-click** on the generated WSDL link and **"Save As"**
4. Save the file as `partner.wsdl.xml`

## Step 3: Upload to Replit

1. **In Replit**: Click the **"Files"** panel on the left sidebar
2. **Drag and drop** both files into the project root:
   - `metadata.wsdl.xml`
   - `partner.wsdl.xml`

## Step 4: Verify Installation

The system will automatically detect these files and use them for enhanced SOAP functionality. You'll see:
```
Found local WSDL file: metadata.wsdl.xml
✓ Successfully initialized SOAP client with local WSDL file
```

## Why This Helps

- **More Reliable**: Local WSDL files avoid network authentication issues
- **Better Performance**: No need to download WSDL on every request
- **Enhanced Features**: Enables full SOAP Metadata API functionality
- **Backup Method**: Provides alternative to CLI-based object creation

## Troubleshooting

If you get XML parsing errors, ensure:
1. Files are saved with `.xml` extension
2. Files contain actual XML content (not HTML error pages)
3. Files are uploaded to the project root directory
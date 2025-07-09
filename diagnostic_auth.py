"""
Salesforce Authentication Diagnostic Tool
Helps troubleshoot common authentication issues
"""
import requests
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

def diagnose_auth_issue(username, password, security_token=None, sandbox=False):
    """
    Diagnose authentication issues with detailed error reporting
    
    Args:
        username (str): Salesforce username
        password (str): Salesforce password  
        security_token (str): Security token (optional)
        sandbox (bool): Whether this is a sandbox environment
        
    Returns:
        dict: Diagnostic results with specific recommendations
    """
    results = {
        "success": False,
        "error_type": None,
        "error_message": None,
        "recommendations": [],
        "next_steps": []
    }
    
    try:
        # Determine login URL
        if sandbox:
            login_url = "https://test.salesforce.com/services/Soap/u/58.0"
            env_type = "Sandbox"
        else:
            login_url = "https://login.salesforce.com/services/Soap/u/58.0"
            env_type = "Production"
        
        # Prepare password with token
        password_with_token = f"{password}{security_token or ''}"
        
        # Create SOAP request
        soap_request = f'''
        <?xml version="1.0" encoding="utf-8" ?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xmlns:urn="urn:partner.soap.sforce.com">
            <soapenv:Body>
                <urn:login>
                    <urn:username>{username}</urn:username>
                    <urn:password>{password_with_token}</urn:password>
                </urn:login>
            </soapenv:Body>
        </soapenv:Envelope>
        '''.strip()
        
        headers = {
            'Content-Type': 'text/xml; charset=UTF-8',
            'SOAPAction': '""'
        }
        
        logger.info(f"Attempting authentication to {env_type} environment")
        logger.info(f"Login URL: {login_url}")
        logger.info(f"Username: {username}")
        logger.info(f"Security token provided: {'Yes' if security_token else 'No'}")
        
        # Make the request
        response = requests.post(login_url, data=soap_request, headers=headers, timeout=30)
        
        # Analyze response
        if response.status_code == 200:
            # Parse successful response
            try:
                root = ET.fromstring(response.content)
                namespaces = {
                    'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                    'partner': 'urn:partner.soap.sforce.com'
                }
                
                result = root.find('.//partner:loginResponse/partner:result', namespaces)
                if result is not None:
                    results["success"] = True
                    results["recommendations"].append("✅ Authentication successful!")
                    return results
                    
            except ET.ParseError as e:
                results["error_type"] = "XML_PARSE_ERROR"
                results["error_message"] = f"Could not parse response: {str(e)}"
                
        else:
            # Parse error response
            try:
                root = ET.fromstring(response.content)
                fault_code = root.find('.//{urn:fault.partner.soap.sforce.com}exceptionCode')
                fault_string = root.find('.//{urn:fault.partner.soap.sforce.com}exceptionMessage')
                
                if fault_code is not None:
                    error_code = fault_code.text
                    error_msg = fault_string.text if fault_string is not None else "Unknown error"
                    
                    results["error_type"] = error_code
                    results["error_message"] = error_msg
                    
                    # Provide specific recommendations based on error type
                    if error_code == "INVALID_LOGIN":
                        results["recommendations"] = [
                            "🔑 **Most likely cause: Missing or incorrect security token**",
                            "📧 Reset your security token: Setup → My Personal Information → Reset Security Token",
                            "🔗 The security token will be emailed to you",
                            "🔐 Either enter the token separately OR append it to your password",
                            "✅ Example: If password is 'mypass123' and token is 'ABCDEF', use 'mypass123ABCDEF'"
                        ]
                        results["next_steps"] = [
                            "1. Log into Salesforce in your browser",
                            "2. Go to Setup → My Personal Information → Reset Security Token", 
                            "3. Click 'Reset Security Token'",
                            "4. Check your email for the new token",
                            "5. Try logging in again with the token appended to your password"
                        ]
                    elif error_code == "API_DISABLED_FOR_ORG":
                        results["recommendations"] = [
                            "🚫 **API access is disabled for your organization**",
                            "👨‍💼 Contact your Salesforce administrator to enable API access",
                            "⚙️ Admin needs to go to Setup → Company Settings → Company Information",
                            "✅ Ensure 'API Enabled' permission is checked for your user profile"
                        ]
                    elif error_code == "LOGIN_MUST_USE_SECURITY_TOKEN":
                        results["recommendations"] = [
                            "🔒 **Security token is required from your IP address**",
                            "📧 Reset your security token: Setup → My Personal Information → Reset Security Token",
                            "🔐 Append the token to your password or enter it separately"
                        ]
                    elif error_code == "INVALID_LOGIN_HOURS":
                        results["recommendations"] = [
                            "⏰ **Login outside allowed hours**",
                            "👨‍💼 Contact your administrator about login hour restrictions",
                            "🕐 Your user profile may have login hour restrictions configured"
                        ]
                    elif error_code == "INVALID_LOGIN_IP":
                        results["recommendations"] = [
                            "🌐 **Login from unauthorized IP address**",
                            "👨‍💼 Contact your administrator to whitelist your IP address",
                            "🔒 Your org has IP restrictions enabled"
                        ]
                    else:
                        results["recommendations"] = [
                            f"❓ **Unknown error code: {error_code}**",
                            "👨‍💼 Contact your Salesforce administrator for assistance",
                            "📋 Share this error code with them for faster resolution"
                        ]
                        
            except ET.ParseError:
                results["error_type"] = "NETWORK_ERROR"
                results["error_message"] = f"HTTP {response.status_code}: {response.text[:200]}..."
                results["recommendations"] = [
                    "🌐 **Network or server error**",
                    "🔄 Check your internet connection", 
                    "⏰ Try again in a few minutes",
                    "🏢 Contact your IT department if issue persists"
                ]
    
    except requests.exceptions.Timeout:
        results["error_type"] = "TIMEOUT"
        results["error_message"] = "Request timed out after 30 seconds"
        results["recommendations"] = [
            "⏰ **Connection timeout**",
            "🌐 Check your internet connection",
            "🔄 Try again in a few minutes"
        ]
    except requests.exceptions.ConnectionError:
        results["error_type"] = "CONNECTION_ERROR"  
        results["error_message"] = "Could not connect to Salesforce"
        results["recommendations"] = [
            "🌐 **Connection failed**",
            "🔍 Check your internet connection",
            "🏢 Check if your firewall blocks HTTPS connections",
            "🔄 Try again in a few minutes"
        ]
    except Exception as e:
        results["error_type"] = "UNKNOWN_ERROR"
        results["error_message"] = str(e)
        results["recommendations"] = [
            "❓ **Unexpected error occurred**",
            "🔄 Try again",
            "👨‍💼 Contact support if issue persists"
        ]
    
    return results


def format_diagnostic_report(results):
    """
    Format diagnostic results into a user-friendly report
    
    Args:
        results (dict): Results from diagnose_auth_issue
        
    Returns:
        str: Formatted HTML report
    """
    if results["success"]:
        return '''
        <div class="alert alert-success">
            <h5><i class="bi bi-check-circle-fill me-2"></i>Authentication Successful!</h5>
            <p>Your credentials are working correctly.</p>
        </div>
        '''
    
    report = f'''
    <div class="alert alert-danger">
        <h5><i class="bi bi-exclamation-triangle-fill me-2"></i>Authentication Failed</h5>
        <p><strong>Error:</strong> {results.get("error_message", "Unknown error")}</p>
        <p><strong>Error Type:</strong> {results.get("error_type", "Unknown")}</p>
    </div>
    '''
    
    if results.get("recommendations"):
        report += '''
        <div class="alert alert-warning">
            <h6><i class="bi bi-lightbulb-fill me-2"></i>Recommendations:</h6>
            <ul class="mb-0">
        '''
        for rec in results["recommendations"]:
            report += f'<li>{rec}</li>'
        report += '</ul></div>'
    
    if results.get("next_steps"):
        report += '''
        <div class="alert alert-info">
            <h6><i class="bi bi-list-check me-2"></i>Next Steps:</h6>
            <ol class="mb-0">
        '''
        for step in results["next_steps"]:
            report += f'<li>{step}</li>'
        report += '</ol></div>'
    
    return report
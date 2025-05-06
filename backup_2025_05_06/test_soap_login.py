import os
import logging
import sys
from salesforce_soap_utils import login_with_username_password

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)

logger = logging.getLogger('test_soap_login')

def test_soap_login():
    # Get credentials from environment or prompt user
    username = input("Enter Salesforce username: ")
    password = input("Enter Salesforce password: ")
    security_token = input("Enter Salesforce security token (leave blank if not needed): ")
    
    # Use empty string if no security token provided
    if not security_token:
        security_token = ''
    
    logger.info(f"Attempting SOAP login for user: {username}")
    
    try:
        # Call the login function
        result = login_with_username_password(username, password, security_token)
        
        logger.info("Login successful!")
        logger.info(f"Session ID: {result['access_token'][:10]}...")
        logger.info(f"Instance URL: {result['instance_url']}")
        logger.info(f"User Info: {result['user_info']}")
        
        return True
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_soap_login()

import os
import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Make API keys available to templates
app.config['SALESFORCE_CLIENT_ID'] = os.environ.get('SALESFORCE_CLIENT_ID', '')
app.config['SALESFORCE_CLIENT_SECRET'] = os.environ.get('SALESFORCE_CLIENT_SECRET', '')
app.config['SALESFORCE_REDIRECT_URI'] = os.environ.get('SALESFORCE_REDIRECT_URI', '')
app.config['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

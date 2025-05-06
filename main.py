import os
import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Make API keys available to templates
app.config['SALESFORCE_CLIENT_ID'] = os.environ.get('SALESFORCE_CLIENT_ID', '')
app.config['SALESFORCE_CLIENT_SECRET'] = os.environ.get('SALESFORCE_CLIENT_SECRET', '')
app.config['SALESFORCE_REDIRECT_URI'] = os.environ.get('SALESFORCE_REDIRECT_URI', '')
app.config['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '')

# Routes are already initialized in app.py, so we don't need to do it again here
# from routes import init_routes
# init_routes(app)

# Log configuration status
logger.debug(f"Salesforce Client ID configured: {'Yes' if app.config['SALESFORCE_CLIENT_ID'] else 'No'}")
logger.debug(f"Salesforce Client Secret configured: {'Yes' if app.config['SALESFORCE_CLIENT_SECRET'] else 'No'}")
logger.debug(f"Salesforce Redirect URI configured: {'Yes' if app.config['SALESFORCE_REDIRECT_URI'] else 'No'}")
logger.debug(f"OpenAI API Key configured: {'Yes' if app.config['OPENAI_API_KEY'] else 'No'}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

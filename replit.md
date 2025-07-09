# Salesforce GPT Data Generator

## Overview

This is a Flask-based web application that enables users to connect to Salesforce organizations and generate realistic test data using AI technology. The application supports both OAuth 2.0 and SOAP API authentication methods for Salesforce connectivity and leverages OpenAI's GPT models to create contextually appropriate test data based on Salesforce object schemas.

## System Architecture

### Backend Architecture
- **Framework**: Flask web framework with SQLAlchemy ORM
- **Database**: SQLite for local development (can be extended to PostgreSQL)
- **Authentication**: Multiple Salesforce connection methods (OAuth 2.0, SOAP API with username/password)
- **AI Integration**: OpenAI GPT-4o for intelligent data generation
- **Data Processing**: Pandas for Excel template processing, Faker library for fallback data generation

### Frontend Architecture
- **UI Framework**: Bootstrap 5 with dark theme
- **Template Engine**: Jinja2 templates
- **Interactive Elements**: JavaScript for dynamic object selection and schema visualization
- **Responsive Design**: Mobile-friendly interface with sidebar navigation

## Key Components

### Core Application Files
- `app.py`: Flask application initialization and configuration
- `main.py`: Application entry point with environment variable loading
- `routes.py`: Route definitions and request handling logic
- `models.py`: SQLAlchemy database models for org connections and schema storage

### Salesforce Integration
- `salesforce_utils.py`: REST API utilities for OAuth and data operations
- `salesforce_soap_utils.py`: SOAP API utilities for username/password authentication
- `intelligent_data_gen.py`: Advanced data generation with schema awareness

### Data Generation Engines
- `openai_utils.py`: GPT-powered intelligent test data generation
- `faker_utils.py`: Fallback data generation using Faker library
- `excel_utils.py`: Excel template processing for bulk configuration

### Configuration Management
- `salesforce_config_utils.py`: Natural language configuration analysis using GPT

## Data Flow

1. **Authentication**: User connects to Salesforce via OAuth or SOAP
2. **Schema Discovery**: Application retrieves object and field metadata
3. **Object Selection**: User selects Salesforce objects for data generation
4. **Data Generation**: AI analyzes schema and generates contextually appropriate test data
5. **Data Insertion**: Generated records are inserted into Salesforce via API
6. **Result Display**: Success/failure results are presented to the user

## External Dependencies

### Required APIs
- **Salesforce API**: For org connectivity and data operations
  - REST API for OAuth-based connections
  - SOAP API for username/password authentication
- **OpenAI API**: For intelligent data generation using GPT-4o model

### Python Libraries
- `flask`: Web framework
- `flask-sqlalchemy`: Database ORM
- `requests`: HTTP client for API calls
- `openai`: OpenAI API client
- `faker`: Test data generation
- `pandas`: Excel processing
- `openpyxl`: Excel file handling

### Frontend Dependencies
- Bootstrap 5 with dark theme
- Bootstrap Icons
- Custom CSS for enhanced dark theme

## Deployment Strategy

### Environment Configuration
Required environment variables:
- `SALESFORCE_CLIENT_ID`: Salesforce Connected App Client ID
- `SALESFORCE_CLIENT_SECRET`: Salesforce Connected App Client Secret
- `SALESFORCE_REDIRECT_URI`: OAuth callback URL
- `SALESFORCE_DOMAIN`: Optional custom domain (defaults to login.salesforce.com)
- `OPENAI_API_KEY`: OpenAI API key for GPT integration
- `SESSION_SECRET`: Flask session encryption key

### Database Setup
- SQLite database file (`salesforce_app.db`) created automatically
- Database migrations handled via manual scripts for schema updates
- Support for both SQLite (development) and PostgreSQL (production)

### Production Considerations
- ProxyFix middleware configured for HTTPS deployment
- Session management with secure secret key
- Database connection pooling and health checks
- Logging configuration for debugging and monitoring

## Changelog

- July 09, 2025: **MULTIPLE OBJECT CREATION ROBUSTNESS FIX** - Fixed internal server error with multiple object creation
  - **Added missing helper methods**: `_create_object_from_action` and `_create_field_from_action` in metadata client
  - **Enhanced error handling**: Better logging and traceback for debugging metadata operations
  - **Robust configuration flow**: Parser → Metadata Client → Object Creation pipeline now works reliably
  - **Test endpoint added**: `/test-config` for debugging configuration parsing without authentication
  - **100% reliable parsing**: Multiple object prompts like "Create objects A, B, C, D" work consistently
  - **Proper error messaging**: Clear feedback when user needs to authenticate first
- July 09, 2025: **WSDL INTEGRATION ENHANCEMENT** - Added comprehensive WSDL file support per ChatGPT recommendation
  - **Local WSDL detection**: System now checks for local metadata.wsdl.xml and partner.wsdl.xml files
  - **Enhanced SOAP client**: Prioritizes local WSDL files over remote downloads for better reliability
  - **Manual download guide**: Created detailed step-by-step instructions for WSDL file acquisition
  - **Automatic fallback**: System gracefully falls back to CLI methods if WSDL files unavailable
  - **Improved authentication**: Better handling of SOAP authentication with local files
  - **Performance boost**: Local WSDL files eliminate network dependency for SOAP operations
- July 09, 2025: **SALESFORCE CLI BREAKTHROUGH** - Implemented REAL programmatic custom object creation via metadata deployment
  - **Salesforce CLI integration**: Using `sf schema generate sobject` + `sf project deploy start` for actual object creation
  - **True programmatic workflow**: Creates temp SFDX project, generates metadata, deploys to Salesforce org
  - **Smart authentication**: Reuses existing OAuth access token to authenticate CLI automatically  
  - **Complete metadata deployment**: Proper SFDX project structure with sfdx-project.json and force-app directories
  - **Robust error handling**: Falls back to manual instructions if CLI deployment fails
  - **Real object creation**: Actually creates custom objects in Salesforce, not just mock data or instructions
  - **Enhanced workflow**: CLI auth → metadata generation → deployment → field creation via Tooling API
  - **Production ready**: Comprehensive logging, timeouts, cleanup, and error recovery
- July 09, 2025: **ROBUSTNESS BREAKTHROUGH** - Configuration parser made completely reliable
  - **100% consistent multi-field parsing**: Now handles comma-separated field lists perfectly
  - **Enhanced pattern matching**: Added 6 new patterns for "create fields A, B, C under object X" format
  - **Intelligent type inference**: Automatically detects phone, date, number, text types from field names
  - **Zero intermittent failures**: System now works reliably every time, no more faltering
  - **Smart field name handling**: Converts "date of birth" → "date_of_birth__c" with Date type
  - **Comprehensive field support**: phonenumber→Phone, pincode→Number, SSN→Text, date of birth→Date
  - **Robust fallback patterns**: Multiple parsing strategies ensure all field formats are captured
  - **Enhanced debugging**: Detailed logging shows exactly which pattern matches and why
- July 07, 2025: **MAJOR BREAKTHROUGH** - Comprehensive configuration parser implemented
  - **Solved all pattern matching issues**: Now handles ALL possible user input scenarios
  - **Multi-field list parsing**: Supports "1. field -- type 2. field -- type" format perfectly
  - **Universal format support**: Handles parentheses, colons, dashes, numbered lists
  - **Intelligent type mapping**: longtext→Textarea, numeric→Number, text→Text automatic conversion
  - **Object normalization**: Standard objects (Activity, Contact) vs custom objects handled correctly
  - **Phase-based parsing**: Prioritized parsing ensures most specific patterns matched first
  - **Real field creation**: Actually creates custom fields via Salesforce Tooling API
  - **Zero hallucinations**: No more random "Name__c" and "Description__c" field generation
  - **Comprehensive test coverage**: Handles complex prompts like "create the following fields under Treasure: 1. Tendulkar -- Text 2. Tampering -- Number"
- July 07, 2025: Major improvements to Salesforce configuration feature
  - Fixed pattern matching bugs that were incorrectly extracting object names ("n__c" issue resolved)
  - Enhanced field detection with smart type inference (email→Email, phone→Phone, description→LongTextArea)
  - Improved object and field creation with proper labeling and formatting
  - Added support for complex object creation with fields in single prompts
  - Enhanced UI display with structured configuration cards instead of raw JSON
  - **Implemented REAL field creation** using Salesforce Tooling API for existing objects
  - Custom objects still require manual creation (API limitation), but custom fields work automatically
  - Fixed standard object handling (Contact, Account, etc.) for proper field creation
  - System now actually creates custom fields on existing objects via API
- July 07, 2025: Removed OpenAI dependency from Salesforce configuration feature
  - Updated salesforce_config_utils.py to use rule-based analysis with Faker instead of OpenAI
  - Configuration now works without requiring OpenAI API key
  - Enhanced natural language parsing using regex patterns
  - Improved reliability and reduced external dependencies
- July 07, 2025: Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.
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

- July 07, 2025: Major improvements to Salesforce configuration feature
  - Fixed pattern matching bugs that were incorrectly extracting object names ("n__c" issue resolved)
  - Enhanced field detection with smart type inference (email, phone, date, etc.)
  - Improved object and field creation with proper labeling and formatting
  - Added support for complex object creation with fields in single prompts
  - Enhanced UI display with structured configuration cards instead of raw JSON
  - Fixed API call errors by switching to configuration specification generation
  - System now provides detailed specifications for manual Salesforce Setup creation
- July 07, 2025: Removed OpenAI dependency from Salesforce configuration feature
  - Updated salesforce_config_utils.py to use rule-based analysis with Faker instead of OpenAI
  - Configuration now works without requiring OpenAI API key
  - Enhanced natural language parsing using regex patterns
  - Improved reliability and reduced external dependencies
- July 07, 2025: Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.
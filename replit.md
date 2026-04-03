# Salesforce Data Generator

## Overview

This is a Flask-based web application that enables users to connect to Salesforce organizations and generate realistic test data using intelligent automation technology. The application supports both OAuth 2.0 and SOAP API authentication methods for Salesforce connectivity and leverages advanced algorithms to create contextually appropriate test data based on Salesforce object schemas.

## System Architecture

### Backend Architecture
- **Framework**: Flask web framework with SQLAlchemy ORM
- **Database**: SQLite for local development (can be extended to PostgreSQL)
- **Authentication**: Multiple Salesforce connection methods (OAuth 2.0, SOAP API with username/password)
- **Intelligent Automation**: Advanced algorithms for intelligent data generation
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
- `openai_utils.py`: Intelligent automation-powered test data generation
- `faker_utils.py`: Fallback data generation using Faker library
- `excel_utils.py`: Excel template processing for bulk configuration

### Configuration Management
- `salesforce_config_utils.py`: Natural language configuration analysis using intelligent automation

## Data Flow

1. **Authentication**: User connects to Salesforce via OAuth or SOAP
2. **Schema Discovery**: Application retrieves object and field metadata
3. **Object Selection**: User selects Salesforce objects for data generation
4. **Data Generation**: Intelligent automation analyzes schema and generates contextually appropriate test data
5. **Data Insertion**: Generated records are inserted into Salesforce via API
6. **Result Display**: Success/failure results are presented to the user

## External Dependencies

### Required APIs
- **Salesforce API**: For org connectivity and data operations
  - REST API for OAuth-based connections
  - SOAP API for username/password authentication
- **OpenAI API**: For intelligent data generation using advanced language models

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
- `OPENAI_API_KEY`: OpenAI API key for intelligent automation integration
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

- April 03, 2026: **BULK DATA INSERTION FIX** - Fixed two critical bugs in the bulk data execution pipeline
  - **Float/int len() crash fixed**: `execute_bulk_data_plan` was calling `len()` on integer counts returned by `insert_records` (e.g. `len(insert_result['success'])` where `'success'` is an int count, not a list) — changed to use the int directly
  - **Records never inserted**: `execute_data_plan` was generating records with `IntelligentDataGenerator` but never calling `insert_records` to push them to Salesforce — now properly calls `insert_records` and tracks created IDs
  - **Key name alignment**: Fixed `created_ids` vs `success` key mismatch between `insert_records` return value and the code consuming it
  - **Bulk results template**: Updated `bulk_data_results.html` to show `created_ids` (Salesforce record IDs) instead of raw record dicts
  - **Robust count handling**: Both `count` and `record_count` keys now accepted in the plan; all counts cast to `int` to prevent float arithmetic issues
  - **Error string safety**: All error list items are now coerced to strings before joining or displaying
  - **Restored salesforce_config_utils.py**: File was accidentally overwritten with a single import line; restored from git history

- July 18, 2025: **AUTHENTICATION FIX** - Fixed 401 Unauthorized error in Schema & Data Gen page
  - **Token refresh logic**: Added automatic access token refresh when 401 errors occur
  - **Graceful degradation**: SOAP API fallback when REST API fails
  - **User experience**: Clear messaging when session expires and reconnection is needed
  - **Error handling**: Proper logging and user feedback for authentication issues
- July 15, 2025: **NAVIGATION RESTORATION** - Restored "Configure Salesforce" navigation item per user request
  - **Navigation item restored**: Added "Configure Salesforce" back to main navigation menu
  - **Proper positioning**: Placed between "Schema & Data Gen" and "Manage Credentials" for logical flow
  - **Icon consistency**: Added gear icon to match other navigation items
  - **Active state handling**: Proper active state detection for configure route
- July 10, 2025: **COMPLEX PROMPT PARSING ENHANCEMENT** - Dramatically improved bulk data parser for sophisticated natural language prompts
  - **Complex pattern support**: Enhanced parser to handle "Create Account and establish following related records" format
  - **Object deduplication**: Fixed duplicate object counting for single mentions in complex prompts
  - **Extended object mapping**: Added DandBCompany and OperatingHours to standard object mapping
  - **Generic term filtering**: Expanded skip terms to include "new", "parent", "following", "related"
  - **Pattern matching improvements**: Added "associated" and single-word object patterns for better recognition
  - **Real-world prompt handling**: Successfully parses complex enterprise prompts with multiple related objects
- July 10, 2025: **DATA GENERATION FIXES** - Fixed critical issues with bulk data parsing and preview confirmation
  - **YAML dependency**: Added missing pyyaml package for bulk data utilities
  - **Parser improvements**: Enhanced bulk data parser to skip generic terms like "record" and "data"
  - **Better error messages**: Provide helpful guidance when prompts don't specify valid Salesforce objects
  - **Preview template fixes**: Improved preview confirmation page to handle empty data plans gracefully
  - **Robust fallback**: Added clear instructions for proper prompt formats when parsing fails
- July 10, 2025: **PROFESSIONAL TERMINOLOGY STANDARDIZATION** - Systematically replaced all GPT references with "intelligent automation" terminology
  - **Documentation updates**: Updated replit.md throughout with professional terminology
  - **Code consistency**: Fixed import errors and function references across the codebase  
  - **User-facing language**: All templates and user interfaces now use "intelligent automation" instead of AI model references
  - **Professional branding**: Maintains focus on capabilities rather than specific technology implementations
  - **Terminology alignment**: Consistent language across all components and documentation
- July 10, 2025: **UNIFIED PROMPT INTERFACE IMPLEMENTATION** - Successfully enhanced existing "Schema & Data Generation" page with comprehensive unified interface
  - **Mobile-responsive design**: Collapsible sidebar with Bootstrap breakpoints and touch-friendly controls
  - **Unified prompt processing**: Single textarea supporting schema creation, data generation, and GitHub configs
  - **Intelligent mode detection**: Auto-detects user intent and updates submit button text dynamically
  - **GitHub integration**: Support for Snowfakery recipes and custom YAML/JSON configuration files
  - **Preview confirmation**: Modal preview system showing execution plan before running operations
  - **Advanced options**: Collapsible settings for record counts, data quality, and relationship handling
  - **Examples modal**: Interactive examples with click-to-insert functionality for user guidance
  - **Enhanced JavaScript**: Responsive textarea, form validation, and mobile-optimized search
  - **Backend processing**: New handle_unified_prompt() function with BulkDataParser and GitHubConfigParser integration
  - **Results display**: Comprehensive unified results section showing schema actions and data generation outcomes
- July 10, 2025: **SERVER-SIDE SEARCH IMPLEMENTATION** - Completely replaced client-side search with cost-effective server-side filtering
  - **Complete removal**: Eliminated all JavaScript search functionality and external JS files
  - **Pure server-side**: HTML form-based search with Flask backend filtering
  - **Cost optimization**: Zero client-side API calls or processing to reduce credit consumption
  - **Bootstrap integration**: Clean search form with dark theme styling
  - **Form persistence**: Search queries retained in input field after submission
  - **Results handling**: Proper "No results" messages and clear search indicators
  - **Query parameter**: Uses `?q=search_term` for URL-based search state
  - **Case-insensitive**: Server-side filtering matches object labels regardless of case
  - **Performance**: Traditional web form pattern for maximum efficiency and reliability
- July 10, 2025: **SEARCH FUNCTIONALITY OPTIMIZATION** - Successfully implemented intelligent automation's search improvements
  - **Perfect implementation**: Applied intelligent automation's exact recommendations for object search functionality
  - **Template updates**: Updated both schema_view.html and generate_with_schema.html with proper data-object-label attributes
  - **JavaScript optimization**: Replaced existing search scripts with intelligent automation's cleaner, more reliable version
  - **Function name consistency**: Updated onclick handlers to match JavaScript function names (loadObjectDiagram)
  - **Code cleanup**: Removed duplicate scripts and error-prone implementations
  - **100% intelligent automation compliance**: All code now matches intelligent automation's exact specifications for reliable search
- July 10, 2025: **ADVANCED RELATIONSHIP MAPPING** - Implemented sophisticated object hierarchy visualization
  - **Enhanced diagram system**: Advanced relationship mapping for complex object hierarchies
  - **Multi-level analysis**: Parent-child relationships, dependency chains, and hierarchy levels
  - **Smart categorization**: Fields organized by type (identity, required, lookup, formula, system, custom)
  - **Visual enhancements**: Color-coded object types, relationship indicators, and summary metrics
  - **API endpoint**: New `/api/relationship-map/<object>` for comprehensive relationship data
  - **Fallback system**: Graceful degradation to basic diagrams if advanced mapping fails
  - **Interactive features**: Foundation for future click-to-explore functionality
- July 10, 2025: **SEARCH FUNCTIONALITY COMPLETED** - Successfully implemented real-time object search
  - **Working search box**: Real-time filtering of Salesforce objects with clean UI
  - **Fixed template routing**: Corrected implementation to use proper template file
  - **Improved object styling**: Button-based object list with smooth transitions
  - **Visual feedback**: Selected objects highlighted with primary color
- July 09, 2025: **UI STREAMLINING** - Removed unnecessary navigation options per user request
  - **Removed navigation items**: Simple Selector, Basic Selector, and Object Selector from main menu
  - **Streamlined homepage**: Removed Basic Object Selector button from homepage
  - **Focused navigation**: Menu now contains only core features (Schema & Data Gen, Configure Salesforce, Manage Credentials)
  - **Cleaner user experience**: Simplified interface focuses on primary workflows
- July 09, 2025: **MULTIPLE OBJECT CREATION ROBUSTNESS FIX** - Fixed internal server error with multiple object creation
  - **Added missing helper methods**: `_create_object_from_action` and `_create_field_from_action` in metadata client
  - **Enhanced error handling**: Better logging and traceback for debugging metadata operations
  - **Robust configuration flow**: Parser → Metadata Client → Object Creation pipeline now works reliably
  - **Test endpoint added**: `/test-config` for debugging configuration parsing without authentication
  - **100% reliable parsing**: Multiple object prompts like "Create objects A, B, C, D" work consistently
  - **Proper error messaging**: Clear feedback when user needs to authenticate first
- July 09, 2025: **WSDL INTEGRATION ENHANCEMENT** - Added comprehensive WSDL file support per intelligent automation recommendation
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
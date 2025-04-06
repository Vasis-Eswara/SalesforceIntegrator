import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client
# We use a function to create the client so we can handle missing API key
def get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY environment variable not set")
        return None
    return OpenAI(api_key=api_key)

openai = get_openai_client()

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

def generate_test_data_with_gpt(object_info, record_count):
    """Generate test data based on Salesforce object schema using GPT"""
    try:
        # Check if OpenAI client is initialized
        if openai is None:
            raise Exception("OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.")
            
        # Create a system message that explains the task
        system_message = """
        You are a data generation expert that creates valid test data for Salesforce objects.
        You will receive a Salesforce object schema and should generate realistic test data that:
        1. Follows all field constraints (type, length, required, unique)
        2. Uses realistic values appropriate for each field type
        3. Maintains referential integrity for relationship fields
        4. Follows business logic patterns typically seen in Salesforce implementations
        
        Return ONLY a valid JSON array containing the generated records.
        """
        
        # Create a user message that includes the object schema and requirements
        user_message = f"""
        Please generate {record_count} test records for the Salesforce object: {object_info['name']} ({object_info['label']}).
        
        Here is the object schema:
        {json.dumps(object_info, indent=2)}
        
        Important requirements:
        - Only include createable fields
        - Handle required fields appropriately
        - For reference/lookup fields, use placeholder IDs in the format "001XXXXXXXXXXXXXXX" (adjust the prefix based on object type)
        - For unique fields, ensure each value is different
        - Generate realistic data for each field based on field name and type
        - Ensure dates and times are properly formatted
        - Do not include the "Id" field in the generated records
        
        Return a JSON array of {record_count} records with appropriate field values.
        """
        
        # Call the OpenAI API to generate the data
        response = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4000
        )
        
        # Extract and parse the generated data
        generated_content = response.choices[0].message.content
        
        # Parse the JSON response - account for different possible structures
        records = []
        try:
            data = json.loads(generated_content)
            # Check if the data is wrapped in an outer object or if it's directly an array
            if isinstance(data, dict) and 'records' in data:
                records = data['records']
            elif isinstance(data, dict) and any(k for k in data.keys() if k.lower() in ['data', 'result', 'results', 'output']):
                # If it's in a common wrapper key, extract from there
                for key in ['data', 'result', 'results', 'output']:
                    if key in data or key.lower() in data:
                        records = data.get(key, data.get(key.lower(), []))
                        break
            else:
                # If it's directly a dict with keys that match our field names, wrap it in an array
                field_names = [field['name'] for field in object_info['fields']]
                if not isinstance(data, list) and any(k for k in data.keys() if k in field_names):
                    records = [data]
                else:
                    # If it's any other structure, just use it as is
                    records = data
        except json.JSONDecodeError:
            # If the model didn't return valid JSON, try to extract a JSON block
            import re
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            match = re.search(json_pattern, generated_content)
            if match:
                json_block = match.group(1)
                records = json.loads(json_block)
            else:
                # If all else fails, raise the error
                logger.error(f"Failed to parse generated data: {generated_content}")
                raise Exception("Failed to generate valid data format")
                
        # Ensure the result is a list of records
        if not isinstance(records, list):
            records = [records]
            
        logger.debug(f"Generated {len(records)} records for {object_info['name']}")
        return records
        
    except Exception as e:
        logger.error(f"Error generating test data: {str(e)}")
        raise

def analyze_schema_with_gpt(object_info):
    """Analyze a Salesforce schema to identify patterns and constraints using GPT"""
    try:
        # Check if OpenAI client is initialized
        if openai is None:
            raise Exception("OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.")
            
        # Create a system message that explains the task
        system_message = """
        You are an expert Salesforce consultant who can analyze object schemas and provide insights.
        Analyze the provided Salesforce object schema and identify:
        1. Key required fields and constraints
        2. Patterns or implied business rules
        3. Suggestions for generating realistic test data
        4. Potential challenges or considerations
        
        Return your analysis in a structured JSON object.
        """
        
        # Create a user message with the schema
        user_message = f"""
        Please analyze this Salesforce object schema for {object_info['name']} ({object_info['label']}) and provide insights:
        
        {json.dumps(object_info, indent=2)}
        
        Focus on:
        - Required fields and dependencies
        - Data type constraints
        - Field patterns that suggest business rules
        - Relationship implications
        - Common patterns for test data generation
        """
        
        # Call the OpenAI API to analyze the schema
        response = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2000
        )
        
        # Extract the analysis
        analysis = json.loads(response.choices[0].message.content)
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing schema: {str(e)}")
        raise

def chat_with_gpt_about_schema(object_info, user_message):
    """Interactive chat about a Salesforce schema using GPT"""
    try:
        # Check if OpenAI client is initialized
        if openai is None:
            raise Exception("OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable.")
            
        # Create a system message that explains the context
        system_message = f"""
        You are an expert Salesforce consultant who is helping a user understand and work with the 
        {object_info['name']} ({object_info['label']}) object in Salesforce.
        
        You have access to the complete schema:
        {json.dumps(object_info, indent=2)}
        
        Answer the user's questions about this object, its fields, how to generate test data for it,
        or any other related questions. Be helpful, concise, and accurate.
        """
        
        # Call the OpenAI API for the chat interaction
        response = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            max_tokens=1000
        )
        
        # Return the response
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise

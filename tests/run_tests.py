"""
Test runner script for running all tests
"""
import os
import sys
import unittest
import pytest
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up the testing environment"""
    # Add the parent directory to the path so imports work correctly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
    sys.path.insert(0, parent_dir)
    
    # Set test database URL to in-memory SQLite
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    # Set test API keys (these won't actually be used since we mock the API calls)
    if 'OPENAI_API_KEY' not in os.environ:
        os.environ['OPENAI_API_KEY'] = 'test_openai_key'
    if 'SALESFORCE_CLIENT_ID' not in os.environ:
        os.environ['SALESFORCE_CLIENT_ID'] = 'test_client_id'
    if 'SALESFORCE_CLIENT_SECRET' not in os.environ:
        os.environ['SALESFORCE_CLIENT_SECRET'] = 'test_client_secret'
    if 'SALESFORCE_REDIRECT_URI' not in os.environ:
        os.environ['SALESFORCE_REDIRECT_URI'] = 'http://localhost:5000/callback'
    
    logger.info(f"Set up test environment with path: {parent_dir}")

def run_tests():
    """Run all the unit tests"""
    print("\n==== Running unit tests for Salesforce Data Generation application ====\n")
    
    setup_environment()
    
    # Define the test suite
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.dirname(__file__), pattern="test_*.py")
    
    # Setup the test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    try:
        # Run the tests
        result = runner.run(suite)
        
        # Print summary
        print("\n==== Test Results Summary ====")
        print(f"- Ran {result.testsRun} tests")
        print(f"- {len(result.errors)} errors")
        print(f"- {len(result.failures)} failures")
        print(f"- {len(result.skipped)} skipped")
        
        success = result.wasSuccessful()
        if success:
            print("\n✅ All tests passed!\n")
        else:
            print("\n❌ Some tests failed. See details above.\n")
        
        # Return a success/failure code
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return 1

def run_pytest():
    """Run all tests using pytest"""
    print("\n==== Running tests with pytest ====\n")
    
    setup_environment()
    
    try:
        # Run pytest on the tests directory with various helpful flags
        result = pytest.main([
            '-v',                           # Verbose output
            '--no-header',                  # Don't show pytest header
            '--tb=native',                  # Use Python's traceback format
            '--color=yes',                  # Color output
            '--durations=5',                # Show 5 slowest tests
            '--cov=.',                      # Show coverage for entire project
            '--cov-report=term-missing',    # Show which lines aren't covered
            os.path.dirname(__file__)       # Test directory
        ])
        
        if result == 0:
            print("\n✅ All tests passed!\n")
        else:
            print("\n❌ Some tests failed. See details above.\n")
        
        return result
    
    except Exception as e:
        logger.error(f"Error running pytest: {e}")
        return 1

def run_single_test(test_name):
    """Run a single test module or test case"""
    print(f"\n==== Running single test: {test_name} ====\n")
    
    setup_environment()
    
    try:
        # Determine if test_name is a file or a specific test
        if os.path.exists(os.path.join(os.path.dirname(__file__), test_name)):
            # It's a file
            result = pytest.main(['-v', os.path.join(os.path.dirname(__file__), test_name)])
        else:
            # It's a specific test
            result = pytest.main(['-v', os.path.dirname(__file__), '-k', test_name])
        
        if result == 0:
            print(f"\n✅ Test {test_name} passed!\n")
        else:
            print(f"\n❌ Test {test_name} failed. See details above.\n")
        
        return result
    
    except Exception as e:
        logger.error(f"Error running single test {test_name}: {e}")
        return 1

if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == 'pytest':
            sys.exit(run_pytest())
        elif sys.argv[1] == 'test' and len(sys.argv) > 2:
            # Run a specific test
            sys.exit(run_single_test(sys.argv[2]))
        else:
            # Assume it's a specific test to run
            sys.exit(run_single_test(sys.argv[1]))
    else:
        sys.exit(run_tests())
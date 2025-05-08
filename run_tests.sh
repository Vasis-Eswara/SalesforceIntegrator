#!/bin/bash
# Script to run tests for the Salesforce Data Generation application

# Install required packages if not installed
echo "Checking for required test packages..."
pip install pytest pytest-mock pytest-cov > /dev/null

# Define color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}"
echo "======================================================"
echo "       SALESFORCE DATA GENERATION APP TEST RUNNER     "
echo "======================================================"
echo -e "${NC}"

# Check command line arguments
if [ "$1" == "help" ] || [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo -e "${YELLOW}Usage:${NC}"
    echo "  ./run_tests.sh            - Run all tests with unittest"
    echo "  ./run_tests.sh pytest     - Run all tests with pytest (with coverage)"
    echo "  ./run_tests.sh <file>     - Run tests in specific file"
    echo "  ./run_tests.sh <name>     - Run specific test by name"
    echo ""
    echo "Examples:"
    echo "  ./run_tests.sh test_faker_utils.py"
    echo "  ./run_tests.sh TestFakerUtils"
    echo "  ./run_tests.sh test_generate_with_valid_object"
    exit 0
fi

# Run the tests through the Python test runner
if [ -z "$1" ]; then
    # No arguments, run all tests with unittest
    echo -e "${BLUE}Running all tests...${NC}"
    python tests/run_tests.py
elif [ "$1" == "pytest" ]; then
    # Run with pytest
    echo -e "${BLUE}Running all tests with pytest and coverage...${NC}"
    python tests/run_tests.py pytest
else
    # Run specific test
    echo -e "${BLUE}Running specific test: $1${NC}"
    python tests/run_tests.py "$1"
fi

# Check exit code
exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}Tests completed successfully!${NC}"
else
    echo -e "${RED}Tests failed with exit code: $exit_code${NC}"
fi

exit $exit_code
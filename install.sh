#!/bin/bash

echo "Setting up HiveMind local environment..."

# Create workspace directories
echo "Creating workspace directories..."
mkdir -p workspace/code
mkdir -p workspace/data
mkdir -p workspace/output

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python is not installed"
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Verify MongoDB
if ! command -v mongod &> /dev/null; then
    echo "Warning: MongoDB is not installed"
    echo "Please install MongoDB and ensure it's running"
else
    echo "MongoDB found"
fi

# Verify RabbitMQ
if ! command -v rabbitmqctl &> /dev/null; then
    echo "Warning: RabbitMQ is not installed"
    echo "Please install RabbitMQ and ensure it's running"
else
    echo "RabbitMQ found"
fi

# Create default .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating default .env file..."
    cat > .env << EOL
# Model Settings
MODEL_NAME=gpt-3.5-turbo
OPENAI_API_KEY=your-api-key-here
TEMPERATURE=0.7
MAX_TOKENS=1000

# Service Connections
MONGODB_URI=mongodb://localhost:27017/
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672

# Workspace Paths
WORKSPACE_ROOT=workspace
SHARED_CODE_DIR=workspace/code
SHARED_DATA_DIR=workspace/data
SHARED_OUTPUT_DIR=workspace/output
EOL
fi

# Make script executable
chmod +x launcher.py

echo
echo "Installation completed!"
echo
echo "Next steps:"
echo "1. Ensure MongoDB is running"
echo "2. Ensure RabbitMQ is running"
echo "3. Update your API key in .env file"
echo "4. Run 'python launcher.py' to start the application"
echo

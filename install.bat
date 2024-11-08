@echo off
echo Setting up HiveMind local environment...

:: Create workspace directories
echo Creating workspace directories...
mkdir workspace 2>nul
mkdir workspace\code 2>nul
mkdir workspace\data 2>nul
mkdir workspace\output 2>nul

:: Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

:: Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

:: Verify MongoDB
echo Checking MongoDB...
mongod --version >nul 2>&1
if errorlevel 1 (
    echo Warning: MongoDB is not installed or not in PATH
    echo Please install MongoDB and ensure it's running
)

:: Verify RabbitMQ
echo Checking RabbitMQ...
rabbitmqctl status >nul 2>&1
if errorlevel 1 (
    echo Warning: RabbitMQ is not installed or not running
    echo Please install RabbitMQ and ensure it's running
)

:: Create default .env if it doesn't exist
if not exist .env (
    echo Creating default .env file...
    echo # Model Settings > .env
    echo MODEL_NAME=gpt-3.5-turbo >> .env
    echo OPENAI_API_KEY=your-api-key-here >> .env
    echo TEMPERATURE=0.7 >> .env
    echo MAX_TOKENS=1000 >> .env
    echo. >> .env
    echo # Service Connections >> .env
    echo MONGODB_URI=mongodb://localhost:27017/ >> .env
    echo RABBITMQ_HOST=localhost >> .env
    echo RABBITMQ_PORT=5672 >> .env
    echo. >> .env
    echo # Workspace Paths >> .env
    echo WORKSPACE_ROOT=workspace >> .env
    echo SHARED_CODE_DIR=workspace/code >> .env
    echo SHARED_DATA_DIR=workspace/data >> .env
    echo SHARED_OUTPUT_DIR=workspace/output >> .env
)

echo.
echo Installation completed!
echo.
echo Next steps:
echo 1. Ensure MongoDB is running
echo 2. Ensure RabbitMQ is running
echo 3. Update your API key in .env file
echo 4. Run this script with 'launch' parameter to start the web interface
echo.

:: Check if launch parameter was provided
if "%1"=="launch" (
    echo Starting HiveMind Web Interface...
    python launch_web.py
    pause
)

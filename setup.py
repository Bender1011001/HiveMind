import os
import subprocess
import shutil

def setup_environment():
    """Setup development environment."""
    print("Setting up HiveMind development environment...")
    
    # Create necessary directories
    directories = ['logs', 'workspace/data', 'workspace/code', 'workspace/output']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")

    # Install dependencies
    print("\nInstalling dependencies...")
    try:
        subprocess.run(['pip', 'install', '-r', 'requirements.txt'], check=True)
        print("Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return

    # Setup configuration
    if not os.path.exists('.env'):
        shutil.copy('.env.example', '.env')
        print("\nCreated .env file. Please update with your settings.")
    else:
        print("\n.env file already exists. Please verify your settings.")

    print("\nEnvironment setup complete!")
    print("\nVerification Checklist:")
    print("- [ ] Update .env file with your API keys and settings")
    print("- [ ] Verify MongoDB connection (default: mongodb://localhost:27017/)")
    print("- [ ] Verify RabbitMQ connection (default: localhost:5672)")
    print("\nTo start the application:")
    print("1. Using Docker: docker-compose up")
    print("2. Without Docker: python run.py")

if __name__ == '__main__':
    setup_environment()

"""Launch script for the HiveMind Web Interface."""

import os
import sys
import webbrowser
from pathlib import Path
import threading
import time

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def open_browser():
    """Open the web interface in the default browser after a short delay."""
    time.sleep(1.5)  # Wait for Flask to start
    webbrowser.open('http://localhost:5000')

def main():
    """Main entry point for launching the web interface."""
    try:
        # Import web app here to ensure all paths are set up correctly
        from src.web.web_app import app
        
        print("Starting HiveMind Web Interface...")
        print("Initializing components...")
        
        # Open browser in a separate thread
        threading.Thread(target=open_browser, daemon=True).start()
        
        # Start Flask application
        print("\nWeb interface available at: http://localhost:5000")
        print("Press Ctrl+C to stop the server")
        
        app.run(
            host='0.0.0.0',  # Allow external access
            port=5000,
            debug=False,     # Disable debug mode for production
            use_reloader=False  # Disable reloader to prevent double browser opening
        )
        
    except KeyboardInterrupt:
        print("\nShutting down HiveMind Web Interface...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError starting web interface: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

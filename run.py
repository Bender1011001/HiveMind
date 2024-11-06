"""Launch script for the HiveMind application."""

import os
import sys
from pathlib import Path
import streamlit.web.cli as stcli

def main():
    """Main entry point for launching the application."""
    # Add project root to Python path
    project_root = Path(__file__).parent
    sys.path.append(str(project_root))
    
    # Set environment variable for module imports
    os.environ["PYTHONPATH"] = str(project_root)
    
    # Launch Streamlit application
    sys.argv = [
        "streamlit",
        "run",
        str(project_root / "src" / "ui" / "app.py"),
        "--server.port=8501",
        "--server.address=localhost"
    ]
    sys.exit(stcli.main())

if __name__ == '__main__':
    main()

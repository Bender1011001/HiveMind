import sys
import streamlit.web.cli as stcli

if __name__ == '__main__':
    sys.argv = ["streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=localhost"]
    sys.exit(stcli.main())

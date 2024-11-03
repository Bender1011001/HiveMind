"""
Main entry point for the LangChain Multi-Agent System.
"""

import streamlit as st
from src.ui.app import main

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")

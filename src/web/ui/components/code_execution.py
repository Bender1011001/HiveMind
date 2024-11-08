"""Code execution component for the HiveMind UI."""

import streamlit as st
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from src.ui.app import MultiAgentUI

class CodeExecution:
    """Component for executing code in the advanced mode interface."""
    
    def __init__(self, parent_ui: 'MultiAgentUI'):
        """Initialize code execution component."""
        self.parent = parent_ui
        self.example_templates = {
            "python": {
                "Hello World": 'print("Hello, World!")',
                "List Operations": """# Create and manipulate a list
numbers = [1, 2, 3, 4, 5]
squared = [x**2 for x in numbers]
print(f"Original: {numbers}")
print(f"Squared: {squared}")""",
                "Function Example": """def greet(name):
    return f"Hello, {name}!"
    
print(greet("User"))"""
            },
            "javascript": {
                "Hello World": 'console.log("Hello, World!");',
                "Array Operations": """// Create and manipulate an array
const numbers = [1, 2, 3, 4, 5];
const squared = numbers.map(x => x**2);
console.log("Original:", numbers);
console.log("Squared:", squared);""",
                "Function Example": """function greet(name) {
    return `Hello, ${name}!`;
}

console.log(greet("User"));"""
            }
        }
        
    def render(self):
        """Render the code execution interface."""
        st.header("Code Execution")
        
        # Code editor
        language = st.selectbox(
            "Programming Language",
            options=["python", "javascript"],
            key="code_language"
        )
        
        self._render_code_editor(language)
        
    def _render_code_editor(self, language: str):
        """Render the code editor interface."""
        example = st.selectbox(
            "Load Example",
            options=["Custom Code"] + list(self.example_templates[language].keys())
        )
        
        if example != "Custom Code":
            code = st.text_area(
                "Code",
                value=self.example_templates[language][example],
                height=200,
                key="code_input"
            )
        else:
            code = st.text_area(
                "Code",
                height=200,
                key="code_input",
                help="Enter your code here"
            )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            run = st.button("▶️ Run")
        with col2:
            st.caption("Press Ctrl+Enter in the code editor to run")
            
        if run or st.session_state.get('run_code', False):
            st.session_state.run_code = False
            if not code.strip():
                st.warning("Please enter some code to execute")
            else:
                try:
                    with st.spinner("Executing code..."):
                        success, output, error = self.parent.code_executor.execute_code(
                            code,
                            language
                        )
                    
                    if success:
                        st.success("✅ Code executed successfully")
                        if output.strip():
                            st.code(output, language=language)
                        else:
                            st.info("(No output)")
                    else:
                        st.error("❌ Code execution failed")
                        st.code(error, language=language)
                    
                except Exception as e:
                    st.error(f"Error executing code: {e}")

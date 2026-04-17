import streamlit as st
import pandas as pd
import base64
from io import BytesIO
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import requests
import json
import time
from PIL import Image
from typing import Dict, Any, Optional
from deep_translator import GoogleTranslator
import re 
import os
import plotly.express as px
import plotly.graph_objects as go
import altair as alt


st.set_page_config(
    
        layout="wide")


st.markdown("""
<style>

/* App background */
.stApp {
    background-color: #F8FAFC;
}

/* Header gradient (brand identity) */
.insightflow-title {
    font-size: 42px;
    font-weight: 700;
    background: linear-gradient(90deg, #2F80ED, #7B61FF, #2DD4BF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Buttons */
.stButton>button {
    background: linear-gradient(90deg, #2F80ED, #7B61FF);
    color: white;
    border-radius: 10px;
    border: none;
    padding: 0.5em 1em;
    font-weight: 500;
}

/* Chat messages */
[data-testid="stChatMessage"] {
    border-radius: 14px;
    padding: 12px;
    margin-bottom: 10px;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    border-radius: 12px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF;
}

/* Expander */
.streamlit-expanderHeader {
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)





class CSVDataRouter:
    def __init__(self):
        # CSV file path - single Global Superstore dataset
        self.csv_files = {
            'global_superstore': 'Global_Superstore2.csv',
        }

        # Ollama configuration with different models
        self.ollama_url = "http://localhost:11434/api/chat"
        self.headers = {'Content-Type': 'application/json'}
        self.classification_model = "llama3.2"  # For query classification
        self.code_model = "deepseek-coder:6.7b"  # For code generation and explanation

        # Add synonym mapping
        self.synonym_mapping = {}
        self.load_synonyms()


    def load_synonyms(self):
        """Load column synonyms from Excel file"""
        try:
            # Look for synonym file in the same directory as the script
            synonym_file = "column_synonyms.xlsx"
            
            if os.path.exists(synonym_file):
                df_synonyms = pd.read_excel(synonym_file)
                
                # Expected format: Column 'original_column' and 'synonyms' (comma-separated)
                for _, row in df_synonyms.iterrows():
                    original_column = row['original_column'].strip()
                    synonyms_str = str(row['synonyms']).strip()
                    
                    if pd.notna(synonyms_str) and synonyms_str != 'nan':
                        # Split synonyms by comma and clean them
                        synonyms = [syn.strip().lower() for syn in synonyms_str.split(',') if syn.strip()]
                        
                        # Map each synonym to the original column
                        for synonym in synonyms:
                            self.synonym_mapping[synonym] = original_column
                            
        except Exception as e:
            # Silently handle errors - no UI feedback needed
            self.synonym_mapping = {}
    
    def enhance_prompt_with_synonyms(self, user_question: str) -> str:
        """Enhance user question by replacing synonyms with actual column names"""
        enhanced_question = user_question.lower()
        
        # Replace synonyms with actual column names
        for synonym, original_column in self.synonym_mapping.items():
            if synonym in enhanced_question:
                enhanced_question = enhanced_question.replace(synonym, original_column)
        
        return enhanced_question





    def determine_query_type(self, user_question: str) -> str:
        """Always return the single Global Superstore dataset"""
        return 'global_superstore'
    
    def execute_query(self, query_type: str) -> Optional[pd.DataFrame]:
        """Load the Global Superstore CSV dataset and return a DataFrame"""
        try:
            df = pd.read_csv(self.csv_files['global_superstore'], encoding='latin-1')
            df['Order Date'] = pd.to_datetime(df['Order Date'], dayfirst=True)
            df['Ship Date'] = pd.to_datetime(df['Ship Date'], dayfirst=True)
            return df
        except FileNotFoundError as e:
            st.error(f"CSV file not found: {str(e)}")
            return None
        except Exception as e:
            st.error(f"Failed to load CSV data: {str(e)}")
            return None


# Initialize the CSV Router
@st.cache_resource
def get_sql_router():
    router = CSVDataRouter()
    # Ensure synonym_mapping is initialized if not present
    if not hasattr(router, 'synonym_mapping'):
        router.synonym_mapping = {}
        router.load_synonyms()
    return router

# Initialize session state variables if they don't exist
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'current_dataset' not in st.session_state:
    st.session_state.current_dataset = None

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()

if 'selected_lang' not in st.session_state:
    st.session_state.selected_lang = "English"

if 'visualization_preferences' not in st.session_state:
    st.session_state.visualization_preferences = {}

# Constants
MODEL = 'llama3.2'

# Function to load data based on user question
def load_data_for_question(user_question):
    """Load appropriate dataset based on user question using MCP logic with synonym support"""
    router = get_sql_router()
    
    # Determine which query to use (this now uses enhanced question internally)
    query_type = router.determine_query_type(user_question)
    
    # Execute the query
    df = router.execute_query(query_type)
    
    if df is not None and not df.empty:
        st.session_state.df = df
        st.session_state.current_dataset = 'global_superstore'
        return True
    else:
        st.error("Failed to load data from CSV file")
        return False


def render_visualization_with_buttons(result, message_index, user_question):
    """Render visualization with toggle buttons and multi-column support"""
    if not isinstance(result, pd.DataFrame):
        st.write(result)
        return

    df = result.copy()
    df.columns = df.columns.str.strip()

    # Create unique key for this message
    viz_key = f"viz_{message_index}"

    # Get current preference or default based on user question
    default_viz = detect_chart_type(user_question.lower()) if user_question else 'table'
    if default_viz == 'default':
        default_viz = 'bar'
    elif default_viz is None:
        default_viz = 'table'

    current_viz = st.session_state.visualization_preferences.get(viz_key, default_viz)

    # Toggle buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Table", key=f"table_{message_index}",
                     type="primary" if current_viz == 'table' else "secondary"):
            st.session_state.visualization_preferences[viz_key] = 'table'
            st.rerun()
    with col2:
        if st.button("📈 Bar Chart", key=f"bar_{message_index}",
                     type="primary" if current_viz == 'bar' else "secondary"):
            st.session_state.visualization_preferences[viz_key] = 'bar'
            st.rerun()
    with col3:
        if st.button("📉 Line Chart", key=f"line_{message_index}",
                     type="primary" if current_viz == 'line' else "secondary"):
            st.session_state.visualization_preferences[viz_key] = 'line'
            st.rerun()

    # Render based on current selection
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = [col for col in df.columns if col not in numeric_cols]

    if current_viz == 'table':
        styled_df = df.style.format({col: "{:,.2f}" for col in numeric_cols})
        st.dataframe(styled_df, use_container_width=True)

    elif current_viz == 'bar':
        if len(numeric_cols) > 0 and len(categorical_cols) > 0:
            col1, col2 = st.columns(2)
            with col1:
                x_col = st.selectbox("X-axis (Category):", categorical_cols, key=f"bar_x_{viz_key}")
            with col2:
                y_cols = st.multiselect("Y-axis (Numeric):", numeric_cols,
                                        default=[numeric_cols[0]], key=f"bar_y_{viz_key}")
            if y_cols:

                colors = ["#2F80ED", "#7B61FF", "#2DD4BF"]
                st.bar_chart(
                    df.set_index(x_col)[y_cols],
                    color=colors[:len(y_cols)]
                )
            else:
                st.warning("Please select at least one numeric column for the Y-axis")

        elif len(numeric_cols) >= 2:
            st.info("💡 No categorical columns found. Select numeric columns to display.")
            y_cols = st.multiselect("Select columns to display:", numeric_cols,
                                    default=[numeric_cols[0]], key=f"bar_y_num_{viz_key}")
            if y_cols:
                st.bar_chart(df[y_cols])
        else:
            st.warning("Bar chart requires at least one numeric column")

    elif current_viz == 'line':
        if len(numeric_cols) > 0 and len(categorical_cols) > 0:
            col1, col2 = st.columns(2)
            with col1:
                x_col = st.selectbox("X-axis (Category):", categorical_cols, key=f"line_x_{viz_key}")
            with col2:
                y_cols = st.multiselect("Y-axis (Numeric):", numeric_cols,
                                        default=[numeric_cols[0]], key=f"line_y_{viz_key}")
            if y_cols:

                colors = [ "#7B61FF", "#2DD4BF", "#2F80ED"]
                st.line_chart(
                        df.set_index(x_col)[y_cols],
                        color=colors[:len(y_cols)]
                        )
            else:
                st.warning("Please select at least one numeric column for the Y-axis")

        elif len(numeric_cols) >= 2:
            st.info("💡 No categorical columns found. Select numeric columns to display.")
            y_cols = st.multiselect("Select columns to display:", numeric_cols,
                                    default=[numeric_cols[0]], key=f"line_y_num_{viz_key}")
            if y_cols:
                st.line_chart(df[y_cols])
        else:
            st.warning("Line chart requires at least one numeric column")



# Function to generate code explanation
def generate_code_explanation(code, user_question):
    """Generate explanation of what the code actually did"""
    explanation_prompt = f"""
    You are a code explanation expert. Based on the user's original question and the Python code that was executed, provide a brief, clear explanation of what the code actually did.

    User's original question: "{user_question}"
    
    Python code that was executed:
    ```python
    {code}
    ```
    
    Provide a concise explanation (1-3 sentences) of:
    1. What data operation was performed
    2. What the result shows or calculates
    
    Keep it simple and user-friendly. Don't repeat the code, just explain what it accomplished.
    """
    
    try:
        payload = {
            "model": "llama3.2",  # Using deepseek-coder
            "messages": [
                {"role": "user", "content": explanation_prompt}
            ],
            "stream": False
        }
        
        response = requests.post("http://localhost:11434/api/chat", 
                               headers={'Content-Type': 'application/json'}, 
                               json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result['message']['content'].strip()
        else:
            return "Code executed successfully."
            
    except Exception as e:
        return "Code executed successfully."

# Create the system message
def get_system_message():
    if st.session_state.df.empty:
        return "No data loaded. Please ask a question to load relevant data."
    
    column_types = {col: str(st.session_state.df[col].dtype) for col in st.session_state.df.columns}
    sample_data = st.session_state.df.head(3).to_dict('records')
    
    # Get router instance to access synonyms - with error handling
    router = get_sql_router()
    synonym_info = ""
    
    # Check if synonym_mapping exists and has content
    if hasattr(router, 'synonym_mapping') and router.synonym_mapping:
        synonym_info = f"\n- Available column synonyms: {dict(list(router.synonym_mapping.items())[:10])}..."
    
    return f"""You are an expert Python data analysis assistant. Your primary goal is to generate precise, executable Python code that answers user queries based on the following specifications:

Context:
- Dataframe name: df
- Current dataset: Global Superstore (orders, sales, profit, shipping data across regions and categories)
- Column names and types: {column_types}
- Sample data (first 3 rows): {sample_data}{synonym_info}

Key columns include: Row ID, Order ID, Order Date, Ship Date, Ship Mode, Customer ID, Customer Name, Segment, City, State, Country, Postal Code, Market, Region, Product ID, Category, Sub-Category, Product Name, Sales, Quantity, Discount, Profit, Shipping Cost, Order Priority

CRITICAL DATAFRAME RULES:
*** THE DATAFRAME 'df' IS ALREADY LOADED AND CONTAINS REAL DATA ***
- NEVER create a new DataFrame using pd.DataFrame()
- NEVER define sample data or mock data
- NEVER reassign the 'df' variable
- The df variable contains {st.session_state.df.shape[0]} rows and {st.session_state.df.shape[1]} columns of real data
- ALWAYS work with the existing 'df' variable directly
- When user mentions column names that might be synonyms, use the actual column names from the dataframe

Code Generation Guidelines:
1. Always include necessary import statements at the top of your code
2. Write clean, efficient, and production-ready Python code
3. Optimize for readability and performance
4. Use appropriate libraries for data analysis (pandas, numpy)
5. Handle potential edge cases and include error handling where applicable
6. When you asked for a TOTAL of a column you must use SUM

CRITICAL RESTRICTIONS:
- NEVER import matplotlib, seaborn, or any plotting libraries
- NEVER use plt, .plot(), .bar(), .figure(), .show(), or any plotting functions
- Do NOT generate any visualization code - the UI handles all charts automatically
- Focus ONLY on data processing and analysis
- NEVER create or define a DataFrame - use the existing 'df' variable

Output Requirements:
- Store your final result in a variable called 'result_output'
- For dataframe results, use result_output = your_dataframe
- For text/numeric results, use result_output = your_result
- Always end your code with: result_output = your_result
- The result_output should contain the processed data that can be displayed or charted by the UI
- All results must be returned as DataFrames, even if it's a single column (e.g., after .groupby().sum() use .reset_index())

EXAMPLE OF CORRECT CODE:
```python
import pandas as pd
import numpy as np

# Work directly with the existing df - DO NOT create a new one
result_output = df.groupby('Category')['Sales'].sum().reset_index()
```

EXAMPLE OF INCORRECT CODE (DO NOT DO THIS):
```python
# WRONG - Don't create DataFrames
df = pd.DataFrame({{'col1': [1,2,3], 'col2': [4,5,6]}})
```

IMPORTANT: Even if the user asks for a chart, bar chart, or visualization, do NOT generate any plotting code. Only prepare the data and store it in result_output. The UI will automatically create the appropriate visualization based on the user's request.

Recommended Libraries:
import pandas as pd
import numpy as np
"""

# Function to extract Python code from response
def extract_code(response_text):
    # Find code blocks (text between ```python and ```)
    code_pattern = r"```python\s*(.*?)\s*```"
    code_blocks = re.findall(code_pattern, response_text, re.DOTALL)
    
    # If no Python code block is found, try looking for code without language specifier
    if not code_blocks:
        code_pattern = r"```\s*(.*?)\s*```"
        code_blocks = re.findall(code_pattern, response_text, re.DOTALL)
    
    # Clean up the code blocks - remove extra whitespace and ensure proper formatting
    cleaned_code_blocks = []
    for code in code_blocks:
        # Strip whitespace and ensure it's a proper string
        cleaned_code = code.strip()
        if cleaned_code:
            cleaned_code_blocks.append(cleaned_code)
    
    # Get all text outside of code blocks to print as message
    other_text = re.sub(r"```.*?```", "", response_text, re.DOTALL).strip()
    
    return cleaned_code_blocks, other_text

# Function to run extracted code
def run_code(code):
    try:
        # Ensure code is a string
        if not isinstance(code, str):
            return "", [], "Code must be a string", None
            
        # Create a local namespace with df already available
        local_namespace = {"df": st.session_state.df, "pd": pd, "st": st, "np": np, 
                          "plt": plt, "sns": sns, "matplotlib": matplotlib}
        
        # Capture stdout for any remaining print statements
        import io
        import sys
        original_stdout = sys.stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Execute the code - ensure it's a string
        exec(str(code), globals(), local_namespace)
        
        # Get the captured output
        execution_result = captured_output.getvalue()
        sys.stdout = original_stdout
        
        # Extract results from the local namespace
        result_output = local_namespace.get('result_output', None)
        
        # For matplotlib plots (fallback)
        plot_images = []
        
        return execution_result, plot_images, None, result_output
    except Exception as e:
        return "", [], str(e), None


# Function to get response from the model using direct HTTP requests
def get_response(message, system_msg=None, model=None):
    url = "http://localhost:11434/api/chat"
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Use provided system message or default
    sys_msg = system_msg if system_msg else get_system_message()
    
    # Use provided model or default to llama3.2
    selected_model = model if model else MODEL  # MODEL is defined as 'llama3.2' in your constants
    
    # Format messages in the expected format for the API
    messages_history = [{"role": "system", "content": sys_msg}]
    
    # Add chat history if using default system message
    if sys_msg == get_system_message():
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                messages_history.append({"role": msg["role"], "content": msg["content"]})
            else:
                # For assistant messages, use the original content
                messages_history.append({"role": msg["role"], "content": msg["content"]})
    
    # Add the new message
    messages_history.append({"role": "user", "content": message})
    
    # Prepare request data
    data = {
        "model": selected_model,  # Use the selected model
        "messages": messages_history,
        "stream": False
    }
    
    # Send the request
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        response_json = response.json()
        response_text = response_json.get("message", {}).get("content", "")
    else:
        response_text = f"Error: API returned status code {response.status_code}"
    
    return response_text


 # Normalize and detect chart type
# Detect chart type
def detect_chart_type(text):
    if re.search(r'\bbar\s?(chart|graph)?\b', text):
        return 'bar'
    elif re.search(r'\bline\s?(chart|graph)?\b', text):
        return 'line'
    elif 'chart' in text or 'plot' in text or 'visual' in text or 'graph' in text:
        return 'default'
    return None

# Define a function: def get_error_correction_system_message():
def get_error_correction_system_message():
# Streamlit session state initialization or access
    if st.session_state.df.empty:
# Return statement
        return "No data loaded for error correction."


# Streamlit session state initialization or access
    column_types = {col: str(st.session_state.df[col].dtype) for col in st.session_state.df.columns}
# Return statement
    return f"""You are a Python debugging expert. Fix the code based on the error message provided. Important details:


- DataFrame 'df' is already loaded - don't include code to load it
# Streamlit session state initialization or access
- Current dataset: Global Superstore
- Available columns and types: {column_types}
- Make sure to include all necessary imports
- Use streamlit (st) commands to display results
- The original error is shown below, fix the code to address this specific error


Your response should only include the corrected Python code block with no additional explanations.
"""



def clean_plotting_code(code):
    """Remove plotting code, DataFrame creation, and ensure proper result_output assignment"""
    lines = code.split('\n')
    cleaned_lines = []
    
    # Track if we have a proper result_output
    has_result_output = False
    data_variable = None
    
    for line in lines:
        line_stripped = line.strip()
        
        # Skip matplotlib/plotting related lines
        if any(keyword in line_stripped for keyword in [
            'import matplotlib', 'import seaborn', 'plt.', '.plot(', '.bar(', '.figure(',
            '.show()', '.tight_layout()', '.xticks(', '.xlabel(', '.ylabel(', '.title('
        ]):
            continue
            
        # Skip DataFrame creation lines
        if any(pattern in line_stripped for pattern in [
            'df = pd.DataFrame(',
            'df=pd.DataFrame(',
            'pd.DataFrame({',
            'column_names = {',
            'column_types = {',
            '# Define the column names',
            '# Define the column types'
        ]):
            continue
            
        # Check for result_output assignment
        if 'result_output' in line_stripped and '=' in line_stripped:
            # If it's a fake assignment (like creating new data), skip it
            if any(keyword in line_stripped for keyword in ['DataFrame({', '[1,2,3]', 'pd.DataFrame']):
                continue
            has_result_output = True
            
        # Track data processing variables
        if '=' in line_stripped and 'df.groupby' in line_stripped:
            data_variable = line_stripped.split('=')[0].strip()
            
        cleaned_lines.append(line)
    
    # If no proper result_output found, add it
    if not has_result_output and data_variable:
        cleaned_lines.append(f'\nresult_output = {data_variable}')
    
    return '\n'.join(cleaned_lines)


def validate_and_fix_code(code):
    """Validate code and remove DataFrame creation attempts"""
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # Skip lines that create DataFrames
        if any(pattern in line_stripped for pattern in [
            'df = pd.DataFrame(',
            'df=pd.DataFrame(',
            'pd.DataFrame({',
            'column_names = {',
            'column_types = {',
            '# Define the column names',
            '# Define the column types'
        ]):
            continue
            
        # Skip comment lines about defining DataFrames
        if line_stripped.startswith('#') and any(keyword in line_stripped.lower() for keyword in [
            'define the column', 'dataframe', 'sample data', 'mock data'
        ]):
            continue
            
        # Skip print statements that aren't result_output
        if 'print(' in line_stripped and 'result_output' not in line_stripped:
            continue
            
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


# Function to handle message processing and display
def process_message(prompt):
    # First, try to load appropriate data based on the question
    # Translate user question from Greek to English
    source_lang = 'auto'
    target_lang = 'en'

    if st.session_state.selected_lang != "English":
        try:
            translated_prompt = GoogleTranslator(source=source_lang, target=target_lang).translate(prompt)
        except Exception as e:
            st.error(f"Translation failed: {str(e)}")
            translated_prompt = prompt
    else:
        translated_prompt = prompt
        
    with st.spinner("Loading relevant data..."):
        data_loaded = load_data_for_question(translated_prompt)
    
    if not data_loaded:
        st.error("Could not load data for your question. Please try again.")
        return
    
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Get response from model
    with st.spinner("Analyzing your data..."):
        # First attempt
        response_text = get_response(translated_prompt)
        code_blocks, explanation = extract_code(response_text)
        
        # Initialize variables to track final code
        final_code = None
        display_content = ""
        execution_result = ""
        plot_images = []
        code_explanation = ""
        
        # Language mapping
        lang_map = {"English": "en", "Greek": "el", "Spanish": "es", "Italian": "it"}
        target_display_lang = lang_map.get(st.session_state.selected_lang, "en")
        
        # If we have code to execute
        if code_blocks:
            # First clean plotting code, then validate DataFrame creation
            plotting_cleaned = clean_plotting_code(code_blocks[0])
            original_code = validate_and_fix_code(plotting_cleaned)
            final_code = original_code
            
            # Execute the converted code
            execution_result, plot_images, error, result_output = run_code(final_code)
            
            # If there's an error, try to fix it
            if error:
                # Create error feedback message
                error_msg = f"The code generated has an error: {error}\n\nHere's the code that needs fixing:\n```python\n{final_code}\n```"
                
                # Get fixed code from model
                fixed_response = get_response(error_msg, get_error_correction_system_message())
                fixed_code_blocks = extract_code(fixed_response)
                
                if fixed_code_blocks:
                    final_code = fixed_code_blocks[0]  # Set final_code to the fixed code
                    # Try running the fixed code
                    execution_result, plot_images, error, result_output = run_code(final_code)
                    
                    # If there's still an error, show the error message
                    if error:
                        error_msg = f"I encountered an error while running the analysis: {error}"
                        display_content = (
                            GoogleTranslator(source='en', target=target_display_lang).translate(error_msg)
                            if target_display_lang != "en" else error_msg
                        )
                    else:
                        display_text = "Analysis completed successfully."
                        explanation_en = generate_code_explanation(original_code, translated_prompt)
                        
                        if target_display_lang != "en":
                            display_content = GoogleTranslator(source='en', target=target_display_lang).translate(display_text)
                            code_explanation = GoogleTranslator(source='en', target=target_display_lang).translate(explanation_en)
                        else:
                            display_content = display_text
                            code_explanation = explanation_en
                else:
                    fallback_msg = "I couldn't generate code to answer your question. Please try again with a clearer question."
                    display_content = (
                        GoogleTranslator(source='en', target=target_display_lang).translate(fallback_msg)
                        if target_display_lang != "en" else fallback_msg
                    )
            else:
                # No error, successful execution
                display_text = "Analysis completed successfully."
                explanation_en = generate_code_explanation(original_code, translated_prompt)
                
                if target_display_lang != "en":
                    try:
                        display_content = GoogleTranslator(source='en', target=target_display_lang).translate(display_text)
                        code_explanation = GoogleTranslator(source='en', target=target_display_lang).translate(explanation_en)
                    except Exception as e:
                        display_content = display_text
                        code_explanation = explanation_en
                else:
                    display_content = display_text
                    code_explanation = explanation_en

    # Add assistant response to history
        message_data = {
    "role": "assistant", 
    "content": response_text,
    "display_content": display_content,
    "plot_images": plot_images,
    "execution_result": execution_result,
    "code_explanation": code_explanation,
    "result_output": result_output,
    "original_code": original_code if 'original_code' in locals() else None,
    "final_code": final_code if 'final_code' in locals() else None,
}
    
    # Add final code for verification
    if final_code:
        message_data["final_code"] = final_code

        
    st.session_state.messages.append(message_data)
    st.rerun()







# Create a layout with columns for the header
col1, col2, col3 = st.columns([1, 3, 1])
# Column 1: Display the logo in the top-left
with col1:
    # Load and display the image
    image_path = r"insightflowAI.png"
    try:
        image = Image.open(image_path)
        st.image(image, width=200)
    except Exception as e:
        st.error(f"Error loading image: {e}")
# Column 2: Display current dataset info
with col2:
    #st.title("🤖 Smart Data Analysis Chat")
    selected_lang = st.selectbox("🌐 Select Language", ["English", "Greek", "Spanish", "Italian"], index=0)
    st.session_state.selected_lang = selected_lang
    # Display current dataset information
    if st.session_state.current_dataset:
        st.success(f"Dataset: Global Superstore | {st.session_state.df.shape[0]} rows, {st.session_state.df.shape[1]} columns")
    else:
        st.info("Ask a question to load the Global Superstore dataset!")
# Column 3: Available datasets info
with col3:
    with st.expander("Available Data"):
        st.write("• **Orders**: Sales, profit, quantity per order")
        st.write("• **Geography**: City, State, Country, Market, Region")
        st.write("• **Products**: Category, Sub-Category, Product Name")
        st.write("• **Customers**: Segment, Customer ID, Customer Name")
        st.write("• **Shipping**: Ship Mode, Ship Date, Order Priority")
# Main content - Chat Interface
st.markdown('<div class="insightflow-title">InsightFlow AI</div>', unsafe_allow_html=True)
st.caption("Turn questions into insights.")
# Create a container for chat messages to better control layout
chat_container = st.container()
# Add a button to clear the chat history at the top
clear_col1, clear_col2 = st.columns([1, 5])
with clear_col1:
    if st.button("Clear Chat"):
       st.session_state.messages = []
       st.session_state.current_dataset = None
       st.session_state.df = pd.DataFrame()
       st.session_state.visualization_preferences = {}  # Clear visualization preferences
       st.rerun()
# Use the chat container to display all messages
with chat_container:
    # Display chat messages
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # For user messages, just show the original message
            if message["role"] == "user":
                st.markdown(message["content"])
            # For assistant messages, show result
            else:
                # If there's a displayable result, show it
                if "display_content" in message:
                    st.markdown(message["display_content"])
                # Show captured dataframe results with chart detection
                user_question = ""
                if i > 0 and st.session_state.messages[i - 1]["role"] == "user":
                    user_question = st.session_state.messages[i - 1]["content"]
                # Render output with toggle buttons
                result = message.get("result_output")
                if isinstance(result, pd.Series):
                    result = result.reset_index()
                render_visualization_with_buttons(result, i, user_question)
                # Show code explanation if available
                if "code_explanation" in message and message["code_explanation"].strip():
                    with st.expander("🔍 What did the code do?", expanded=False):
                        st.info(message["code_explanation"])
                # Show original and converted code blocks
                if "original_code" in message and message["original_code"]:
                    with st.expander("📝 Generated Code (Original)", expanded=False):
                        st.code(message["original_code"], language="python")
                # Display any plots
                if "plot_images" in message and message["plot_images"]:
                    for fig in message["plot_images"]:
                        st.pyplot(fig)
                # Show execution result if available (for any print statements that weren't converted)
                #if "execution_result" in message and message["execution_result"].strip():
                #    with st.expander("📋 Console Output", expanded=False):
                #        st.code(message["execution_result"], language="plaintext")
# Add a separator to ensure the input is visually separated
st.markdown("---")

# Frequently Asked Questions - clickable buttons
if 'faq_prompt' not in st.session_state:
    st.session_state.faq_prompt = None

FAQ_QUESTIONS = [
    "What is the total sales for each category?",

    "Who are the top 10 customers by profit?",

    "Which region has the highest number of orders?",

    "What is the average shipping cost per ship mode?",

    "Show me total sales by date",

    "Compare total sales and profit across all markets",

    "What is the average days between order date and ship date per ship mode?"
]

with st.expander("💡 Frequently Asked Questions", expanded=not bool(st.session_state.messages)):
    cols = st.columns(2)
    for idx, question in enumerate(FAQ_QUESTIONS):
        with cols[idx % 2]:
            if st.button(question, key=f"faq_{idx}", use_container_width=True):
                st.session_state.faq_prompt = question
                st.rerun()

# Place the chat input at the bottom of the page
prompt = st.chat_input("Ask a question about sales, profit, customers, products, regions...")

# Handle FAQ button click or typed prompt
if st.session_state.faq_prompt:
    faq_q = st.session_state.faq_prompt
    st.session_state.faq_prompt = None
    process_message(faq_q)
elif prompt:
    process_message(prompt)
import streamlit as st
import pandas as pd
from pathlib import Path
import requests
import os

# Azure OpenAI API details
api_endpoint = "https://infraprototype.openai.azure.com/openai/deployments/Finalprototype/chat/completions?api-version=2024-02-15-preview"
api_key = 'fa7200260a074193b9e1ddac77586e15'  # Replace with your actual API key

# Columns to be analyzed (you can adjust these as needed)
columns_to_analyze = [
    "VMName", "State", "MemoryAssignedGB", "Uptime", "Path", "CreationTime", "HardDrives", "VhdSizeGB",
    "VhdSizeOnDiskGB", "IPAddresses"
]

# Custom CSS for styling
st.markdown(
    """
    <style>
        body {
            background-image: url('https://wallpaper.dog/large/5560230.png');
            background-size: cover;
        }
        .stApp {
            background-color: rgba(0, 0, 0, 0.5);
            color: white;
        }
        .login-box {
            background: rgba(255, 255, 255, 0.7);
            padding: 20px;
            border-radius: 10px;
        }
        .warning-message {
            color: red;
            font-size: 14px;
            margin-top: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Function to authenticate user
def authenticate(username, password):
    return username == "admin" and password == "admin"

# Function to clean and structure CSV data
def clean_csv_data(file_path):
    df = pd.read_csv(file_path)
    for column in df.columns:
        df[column] = df[column].astype(str).str.replace('\n', ' ').str.strip()
    return df[columns_to_analyze]

# Function to load and clean CSV files
def load_and_clean_csv_files(folder_path):
    csv_files = list(Path(folder_path).glob("*.csv"))
    dataframes = {}
    for file in csv_files:
        df = clean_csv_data(file)
        dataframes[file.stem] = df
    return dataframes

# Function to summarize VM data
def summarize_vm_data(df, max_rows=25):
    return df.head(max_rows).to_string(index=False)

# Function to filter data based on query
def filter_data_by_query(df, query):
    if "running" in query.lower():
        df = df[df['State'].str.lower() == 'running']
    elif "off" in query.lower():
        df = df[df['State'].str.lower() == 'off']
    elif "pavan" in query.lower():
        df = df[df['record'].str.contains("pavan", case=False)]
    return df

# Function to interact with Azure OpenAI using CSV data
def get_openai_response(history, vm_name, df, query):
    try:
        # Filter data based on query
        df_filtered = filter_data_by_query(df, query)

        # Construct conversation history for prompt
        history_prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-5:]])  # Limit history to last 5 messages

        # Summarize data for the prompt
        data_summary = summarize_vm_data(df_filtered, max_rows=10)  # Limit summary to 10 rows

        # Construct prompt
        prompt = f"""
        You are an assistant that provides information based on the VM database. Here are the relevant records from the database:
        {data_summary}

        Conversation History:
        {history_prompt}

        User Query: {query}

        Please provide a detailed and accurate response based on the data above.
        """

        headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,  # Adjust max tokens to fit within limits
            "temperature": 0.7,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "top_p": 0.95,
            "stop": None
        }

        response = requests.post(api_endpoint, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 401:
            return "Error: Unauthorized. Please check your API key and permissions."
        elif response.status_code == 400:
            return f"Error: Bad Request. {response.json().get('error', {}).get('message', 'Unknown error')}"
        elif response.status_code == 429:
            return "Error: You exceeded your current quota, please check your plan and billing details."
        else:
            return f"HTTP error occurred: {http_err}"
    except Exception as e:
        return f"Error: {str(e)}"

# Function to plot metrics
def plot_metrics(df):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2, figsize=(10, 10))
    df['MemoryAssignedGB'].plot(kind='bar', ax=ax[0, 0], title='Memory Assigned (GB)')
    df['HardDrives'].value_counts().plot(kind='bar', ax=ax[0, 1], title='Hard Drives')
    df['VhdSizeGB'].plot(kind='bar', ax=ax[1, 0], title='VHD Size (GB)')
    df['VhdSizeOnDiskGB'].plot(kind='bar', ax=ax[1, 1], title='VHD Size on Disk (GB)')
    st.pyplot(fig)

# Path to your CSV files folder (current directory)
csv_folder_path = "."

# Load and clean CSV files
dataframes = load_and_clean_csv_files(csv_folder_path)

# Streamlit application
st.title("VM Management System")

# Login page
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if authenticate(username, password):
            st.session_state['authenticated'] = True
            st.success("Logged in successfully")
        else:
            st.error("Invalid username or password")

    # Warning message
    st.markdown(
        """
        <div class="warning-message">
            Unauthorized login attempts will be tracked and are punishable under law. Please proceed only if you are an authorized user.
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["AI Assistant", "Dashboard", "Download"])

    if page == "AI Assistant":
        st.subheader("AI Assistant")
        st.write("Interact with the AI Assistant for the details of the VMs.")

        # Select a VM (CSV file)
        vm_selected = st.selectbox("Select a VM", list(dataframes.keys()))
        df = dataframes[vm_selected]

        # Initialize conversation history in session state
        if 'conversation_history' not in st.session_state:
            st.session_state['conversation_history'] = []

        # User query input
        query = st.text_input("Enter your query", key="user_query_input")

        # Function to handle new queries
        def handle_new_query():
            new_query = st.session_state['new_query']
            if new_query:
                response = get_openai_response(st.session_state['conversation_history'], vm_selected, df, new_query)
                st.session_state['conversation_history'].append({"role": "user", "content": new_query})
                st.session_state['conversation_history'].append({"role": "assistant", "content": response})
                st.session_state['new_query'] = ""  # Clear the input box for continuous query

        if st.button("Submit"):
            if query:
                st.session_state['conversation_history'].append({"role": "user", "content": query})
                response = get_openai_response(st.session_state['conversation_history'], vm_selected, df, query)
                st.session_state['conversation_history'].append({"role": "assistant", "content": response})

        # Display conversation history
        for message in st.session_state['conversation_history']:
            if message['role'] == 'user':
                st.write(f"**You:** {message['content']}")
            else:
                st.write(f"**AI:** {message['content']}")

        # Continuous input for additional queries
        if 'new_query' not in st.session_state:
            st.session_state['new_query'] = ""

        st.text_input("Your query:", key="new_query", on_change=handle_new_query)

    if page == "Dashboard":
        st.subheader("Dashboard")
        selected_server = st.selectbox("Select a server", list(dataframes.keys()))
        filter_option = st.radio("Filter VMs by State", ("Running", "Off"))
        if selected_server:
            df = dataframes[selected_server]
            if filter_option == "Running":
                filtered_df = df[df['State'] == 'Running']
            else:
                filtered_df = df[df['State'] == 'Off']

            st.dataframe(filtered_df[['VMName', 'State', 'MemoryAssignedGB', 'Uptime', 'CreationTime', 'VhdSizeGB', 'VhdSizeOnDiskGB']])
            
            # Plot metrics
            plot_metrics(filtered_df)

    if page == "Download":
        st.subheader("Download Data")
        selected_server = st.selectbox("Select a server to download its data", list(dataframes.keys()))
        if selected_server:
            df = dataframes[selected_server]
            st.download_button(
                label="Download CSV",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=f"{selected_server}.csv",
                mime='text/csv'
            )

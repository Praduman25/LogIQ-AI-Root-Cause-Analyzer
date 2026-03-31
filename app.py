import streamlit as st

st.set_page_config(page_title="AI RCA System", layout="centered")

st.title("🔍 AI Root Cause Analysis System")

st.write("Upload your logs or paste them below to analyze.")

# Text input
logs = st.text_area("Enter logs here:")

# Button
if st.button("Analyze"):
    st.write("🚀 Analysis will appear here...")
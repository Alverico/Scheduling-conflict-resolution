import streamlit as st
import pandas as pd
import os
from streamlit_lottie import st_lottie
import json
from io import BytesIO

# ------------------ LOTTIE ANIMATIONS ------------------ #
def load_lottie_file(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        st.warning(f"Animation file not found: {filepath}")
        return None

def show_lottie_animation(path, height=300):
    lottie = load_lottie_file(path)
    if lottie:
        st_lottie(lottie, height=height)
    else:
        st.error("❌ Failed to load animation.")

# ------------------ FILE PROCESSING ------------------ #
def process_uploaded_file(uploaded_file):
    try:
        file_extension = uploaded_file.name.split('.')[-1].lower()

        if file_extension == 'csv':
            df = pd.read_csv(uploaded_file)
        elif file_extension in ['xls', 'xlsx']:
            raw_df = pd.read_excel(uploaded_file, header=None)
            header_row = None
            for i in range(min(15, len(raw_df))):
                row = raw_df.iloc[i].astype(str).str.lower()
                if row.str.contains("roll no|registration number|reg no|roll number").any():
                    header_row = i
                    break
            if header_row is not None:
                df = pd.read_excel(uploaded_file, header=header_row)
            else:
                st.error("Could not detect a proper header row containing a roll number identifier. Please check the file.")
                return None
        else:
            st.error("Unsupported file format. Please upload a .csv or .xlsx file.")
            return None

        df.columns = [str(col).strip().lower() for col in df.columns]

        roll_column_candidates = ['roll no', 'roll number', 'registration number', 'reg no']
        matched_col = next((col for col in df.columns if col in roll_column_candidates), None)

        if not matched_col:
            st.error(f"The uploaded file must contain a 'Roll No' or equivalent column. Columns found: {df.columns.tolist()}")
            return None

        df.rename(columns={matched_col: 'roll no'}, inplace=True)

        return df
    except Exception as e:
        st.error(f"Error processing {uploaded_file.name}: {e}")
        return None

# ------------------ BATCH FORMATION ------------------ #
def form_batches_by_subject(uploaded_files, batch_size):
    subject_batches = {}

    for file in uploaded_files:
        subject_name = os.path.splitext(file.name)[0].upper()
        df = process_uploaded_file(file)
        if df is not None:
            df = df[['division', 'roll no', 'student name']]
            df = df.reset_index(drop=True)
            df['Batch'] = [f"{subject_name}{(i // batch_size) + 1}" for i in range(len(df))]
            subject_batches[subject_name] = df

    return subject_batches

# ------------------ MAIN STREAMLIT APP ------------------ #
st.set_page_config(page_title="PCCOE ENTC Timetable Formulator", layout="centered")
st.title("\U0001F4D8 PCCOE ENTC Timetable Formulator")

st.sidebar.header("\U0001F39E️ Animations")
if st.sidebar.checkbox("Show Batch Formation Animation"):
    show_lottie_animation("animations/batch.json")
if st.sidebar.checkbox("Show Timetable Animation"):
    show_lottie_animation("animations/timetable.json")
if st.sidebar.checkbox("Show Conflict Resolution Animation"):
    show_lottie_animation("animations/conflict.json")

st.markdown("### Step 1: Upload Subject Allocation Files")
uploaded_files = st.file_uploader(
    "Upload multiple subject allocation files (.csv/.xlsx)",
    type=["csv", "xls", "xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    st.markdown("### Step 2: Forming Batches")
    batch_size = st.number_input("Enter batch size", min_value=5, max_value=100, value=20, step=5)
    if st.button("Generate Batches"):
        subject_batches = form_batches_by_subject(uploaded_files, batch_size)

        for subject, df in subject_batches.items():
            st.markdown(f"#### Batches for {subject}")
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"Download {subject} Batches as CSV",
                data=csv,
                file_name=f"{subject}_batches.csv",
                mime='text/csv'
            )
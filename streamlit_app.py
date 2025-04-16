import streamlit as st
import pandas as pd
import numpy as np
import random
import os
import re
from io import BytesIO

# ------------------ FILE PROCESSING ------------------ #
def process_uploaded_file(uploaded_file):
    try:
        ext = uploaded_file.name.split('.')[-1].lower()
        if ext == 'csv':
            df = pd.read_csv(uploaded_file)
        elif ext in ['xls', 'xlsx']:
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
                st.error("Could not detect header row.")
                return None
        else:
            st.error("Unsupported file format.")
            return None

        df.columns = [str(col).strip().lower() for col in df.columns]
        roll_candidates = ['roll no', 'roll number', 'registration number', 'reg no']
        matched_col = next((col for col in df.columns if col in roll_candidates), None)

        if not matched_col:
            st.error(f"Roll number column missing. Found: {df.columns.tolist()}")
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
        subject = os.path.splitext(file.name)[0].upper()
        df = process_uploaded_file(file)
        if df is not None:
            df = df[['division', 'roll no', 'student name']]
            df = df.reset_index(drop=True)
            df['Batch'] = [f"{subject}{(i // batch_size) + 1}" for i in range(len(df))]
            subject_batches[subject] = df
    return subject_batches

# ------------------ CONFLICT DETECTION ------------------ #
def detect_conflicts(student_batches_df, timetable):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    conflicts = []

    student_batches_df['Batch Number'] = student_batches_df['Batch Number'].astype(str).str.replace(" ", "").str.upper()
    known_batches = set(student_batches_df['Batch Number'].unique())

    for day in days:
        if day not in timetable.columns:
            continue

        daily_schedule = timetable[["Class time", day]].dropna()
        for _, row in daily_schedule.iterrows():
            time_slot = str(row["Class time"]).strip()
            raw_batches = [x.strip().replace(" ", "").upper() for x in str(row[day]).split(";") if x.strip()]
            active_batches = [b for b in raw_batches if b in known_batches]

            filtered = student_batches_df[student_batches_df["Batch Number"].isin(active_batches)]
            dupes = filtered["Registration Number"].value_counts()
            conflicts_regs = dupes[dupes > 1].index.tolist()

            for reg in conflicts_regs:
                student_info = filtered[filtered["Registration Number"] == reg].iloc[0]
                overlapping = filtered[filtered["Registration Number"] == reg]["Batch Number"].tolist()
                conflicts.append({
                    "Student Name": student_info["Student Name"],
                    "Registration Number": reg,
                    "Division": student_info["Division"],
                    "Day": day,
                    "Time Slot": time_slot,
                    "Conflicting Batches": ", ".join(overlapping)
                })
    return pd.DataFrame(conflicts)

# ------------------ STREAMLIT APP ------------------ #
st.set_page_config(page_title="PCCOE Timetable Formulator", layout="centered")
st.title("📘 PCCOE Batch Formation and Conflict Detection")

st.markdown("### Step 1: Upload Subject Allocation Files")
uploaded_files = st.file_uploader("Upload subject allocation files (.csv/.xlsx)", type=["csv", "xls", "xlsx"], accept_multiple_files=True)

if uploaded_files:
    st.markdown("### Step 2: Form Batches")
    batch_size = st.number_input("Enter batch size", min_value=5, max_value=100, value=20, step=5)
    if st.button("Generate Batches"):
        st.session_state.subject_batches = form_batches_by_subject(uploaded_files, batch_size)

if "subject_batches" in st.session_state:
    st.markdown("### ✅ Batch Formation Results")
    for subject, df in st.session_state.subject_batches.items():
        st.markdown(f"#### Batches for {subject}")
        st.dataframe(df)

    st.markdown("---")
    st.markdown("### Step 3: Upload Timetable Template")
    timetable_file = st.file_uploader("Upload the timetable Excel file", type=["xls", "xlsx"], key="timetable")

    if timetable_file:
        timetable_template = pd.read_excel(timetable_file)
        timetable_template.columns = timetable_template.columns.str.strip()
        st.success("✅ Timetable Template Loaded")

        combined_batches = []
        for subject, df in st.session_state.subject_batches.items():
            temp_df = df.copy()
            temp_df["Course"] = subject
            temp_df.rename(columns={"roll no": "Registration Number", "student name": "Student Name", "Batch": "Batch Number", "division": "Division"}, inplace=True)
            combined_batches.append(temp_df[["Division", "Batch Number", "Registration Number", "Student Name", "Course"]])
        student_batches_df = pd.concat(combined_batches, ignore_index=True)
        student_batches_df["Batch Number"] = student_batches_df["Batch Number"].str.replace(" ", "").str.upper()

        st.session_state["uploaded_timetable"] = timetable_template
        st.markdown("#### Uploaded Timetable")
        st.dataframe(timetable_template)
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            timetable_template.to_excel(writer, index=False)
        st.download_button(
            "Download Uploaded Timetable",
            data=out.getvalue(),
            file_name="Uploaded_Timetable.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        st.markdown("### Step 4: Conflict Detection")
        if st.button("Check for Conflicts"):
            conflict_df = detect_conflicts(student_batches_df, st.session_state["uploaded_timetable"])
            if not conflict_df.empty:
                st.warning("⚠️ Conflicts Detected!")
                st.dataframe(conflict_df)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    conflict_df.to_excel(writer, index=False)
                st.download_button(
                    "Download Conflict Report",
                    data=output.getvalue(),
                    file_name="Detected_Conflicts.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            else:
                st.success("✅ No conflicts detected!")
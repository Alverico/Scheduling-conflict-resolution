import streamlit as st
import pandas as pd
from datetime import datetime

# --- Page Setup ---
st.set_page_config(page_title="📘 PCCOE ENTC Timetable Formulator", layout="wide")

# --- Theme Toggle ---
theme = st.sidebar.radio("🎨 Choose Theme", ["Light", "Dark"])

if theme == "Dark":
    st.markdown("""
        <style>
        body { background-color: #0e1117; color: #fafafa; }
        .stApp { background-color: #0e1117; }
        .block-container { padding-top: 2rem; }
        .stDataFrame { background-color: #1f222a; color: #fafafa; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; }
        </style>
    """, unsafe_allow_html=True)

# --- Animated Conflict Highlighting CSS ---
st.markdown("""
    <style>
    .conflict-highlight {
        animation: flash 1s infinite;
        background-color: #ffe4e1 !important;
    }
    @keyframes flash {
        0%   { background-color: #ffe4e1; }
        50%  { background-color: #ffcccc; }
        100% { background-color: #ffe4e1; }
    }
    </style>
""", unsafe_allow_html=True)

# --- Header ---
col1, col2 = st.columns([1, 8])
with col1:
    st.image("PCCOE-Logo-24-removebg-preview.png", width=90)
with col2:
    st.markdown("## ✨ PCCOE ENTC Timetable Formulator")
    st.markdown("#### _Plan Smart · Detect Conflicts · Form Perfect Batches_")

# --- Sidebar Upload Section ---
with st.sidebar:
    st.header("📂 Upload Files")
    subject_file = st.file_uploader("📘 Subject Allocation File", type=["xlsx"])
    timetable_file = st.file_uploader("⏰ Timetable File", type=["xlsx"])
    st.markdown("💡 *Upload both files to proceed.*")

# --- Helper: Parse time strings ---
def parse_time(time_str):
    try:
        return datetime.strptime(str(time_str), "%H:%M").time()
    except:
        return datetime.strptime(str(time_str), "%H:%M:%S").time()

# --- Conflict Detection ---
def detect_conflicts(subject_df, timetable_df):
    merged_df = pd.merge(subject_df, timetable_df, on="Subject Code", how="left")
    merged_df['Start Time'] = merged_df['Start Time'].apply(parse_time)
    merged_df['End Time'] = merged_df['End Time'].apply(parse_time)

    conflicts = []
    grouped = merged_df.groupby("Student Roll No")
    for roll_no, group in grouped:
        group = group.sort_values(by=["Day", "Start Time"])
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                row1 = group.iloc[i]
                row2 = group.iloc[j]
                if row1['Day'] != row2['Day']:
                    continue
                overlap = (
                    row1['Start Time'] < row2['End Time'] and
                    row2['Start Time'] < row1['End Time']
                )
                if overlap:
                    conflicts.append({
                        "Student Roll No": roll_no,
                        "Subject 1": row1['Subject Code'],
                        "Subject 2": row2['Subject Code'],
                        "Day": row1['Day'],
                        "Time 1": f"{row1['Start Time']} - {row1['End Time']}",
                        "Time 2": f"{row2['Start Time']} - {row2['End Time']}"
                    })
    return pd.DataFrame(conflicts)

# --- Suggest Resolutions ---
def suggest_resolutions(conflict_df, timetable_df):
    suggestions = []
    for _, row in conflict_df.iterrows():
        subj_to_reschedule = row["Subject 2"]
        day_of_conflict = row["Day"]

        alt_slots = timetable_df[
            (timetable_df["Subject Code"] == subj_to_reschedule) &
            (timetable_df["Day"] != day_of_conflict)
        ]

        if not alt_slots.empty:
            first_alt = alt_slots.iloc[0]
            suggestions.append({
                **row,
                "Suggested New Day": first_alt['Day'],
                "Suggested New Time": f"{first_alt['Start Time']} - {first_alt['End Time']}"
            })
        else:
            suggestions.append({
                **row,
                "Suggested New Day": "None",
                "Suggested New Time": "No alternative slot"
            })
    return pd.DataFrame(suggestions)

# --- Batch Formation ---
def form_batches(subject_df, batch_size=30):
    subject_batches = []
    grouped = subject_df.groupby('Subject Code')

    for subject, group in grouped:
        students = group['Student Roll No'].tolist()
        num_batches = (len(students) + batch_size - 1) // batch_size

        for i in range(num_batches):
            batch_students = students[i * batch_size : (i + 1) * batch_size]
            for roll in batch_students:
                subject_batches.append({
                    'Subject Code': subject,
                    'Batch No': f"{subject}_B{i+1}",
                    'Student Roll No': roll
                })

    return pd.DataFrame(subject_batches)

# --- Main Logic ---
if subject_file and timetable_file:
    subject_df = pd.read_excel(subject_file)
    timetable_df = pd.read_excel(timetable_file)

    tab1, tab2 = st.tabs(["🧠 Conflict Detection", "👥 Batch Formation"])

    with tab1:
        with st.expander("📄 Uploaded Data Preview", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📘 Subject Allocation**")
                st.dataframe(subject_df, use_container_width=True)
            with col2:
                st.markdown("**⏰ Timetable Data**")
                st.dataframe(timetable_df, use_container_width=True)

        st.subheader("🚨 Detected Conflicts")
        conflict_df = detect_conflicts(subject_df, timetable_df)

        if not conflict_df.empty:
            st.warning(f"⚠️ {len(conflict_df)} conflicts found!")
            
            # 🎞️ Animate rows by highlighting via HTML table
            styled_conflicts = conflict_df.to_html(classes="conflict-highlight", index=False, escape=False)
            st.markdown(styled_conflicts, unsafe_allow_html=True)

            st.subheader("🛠 Suggested Resolutions")
            resolved_df = suggest_resolutions(conflict_df, timetable_df)
            st.dataframe(resolved_df, use_container_width=True)

            st.download_button(
                "📥 Download Conflict Resolution Report",
                resolved_df.to_csv(index=False),
                file_name="conflict_resolutions.csv",
                mime="text/csv"
            )
        else:
            st.success("✅ No conflicts found!")

    with tab2:
        st.subheader("👥 Generate Student Batches")
        batch_size = st.slider("🎯 Select Batch Size", min_value=5, max_value=100, value=30, step=5)
        batch_df = form_batches(subject_df, batch_size)

        st.dataframe(batch_df, use_container_width=True)

        st.download_button(
            "📥 Download Batch Allocation",
            batch_df.to_csv(index=False),
            file_name="batch_allocation.csv",
            mime="text/csv"
        )
else:
    st.info("👈 Please upload both Subject Allocation and Timetable files to get started.")

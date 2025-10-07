import streamlit as st
import pandas as pd
from utility_attendance import split_file   # <-- using your existing function


def stepwise_file_upload(labels=None, key_prefix="demo"):
    """
    Stepwise uploader for multiple files.
    Each file is requested one by one.
    """
    if labels is None:
        labels = ["File1", "File2"]

    dfs_key = f"{key_prefix}_dfs"
    idx_key = f"{key_prefix}_index"

    # Reset button
    if st.button("🔄 Reset Uploads"):
        st.session_state.pop(dfs_key, None)
        st.session_state.pop(idx_key, None)
        st.rerun()

    # Initialize
    if dfs_key not in st.session_state:
        st.session_state[dfs_key] = {}
        st.session_state[idx_key] = 0

    current_index = st.session_state[idx_key]

    # All done
    if current_index >= len(labels):
        return st.session_state[dfs_key]

    label = labels[current_index]

    uploaded_file = st.file_uploader(
        f"Upload {label} file:",
        type=["csv", "xlsx", "xls"],
        key=f"{key_prefix}_uploader_{current_index}"
    )

    if uploaded_file:
        try:
            # Special case: LEAVE report
            if label == "LEAVE":
                df = pd.read_csv(uploaded_file, skiprows=6, encoding="windows-1252")
            elif uploaded_file.name.lower().endswith(".csv"):
                try:
                    df = pd.read_csv(uploaded_file, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(uploaded_file, encoding="latin-1")
            else:
                df = pd.read_excel(uploaded_file)

            # Save and move forward
            st.session_state[dfs_key][label] = df
            st.session_state[idx_key] += 1
            st.rerun()

        except Exception as e:
            st.error(f"❌ Failed to read {uploaded_file.name}: {e}")

    return st.session_state[dfs_key]


def main():
    st.title("📊 Attendance Upload Demo (5 Files)")

    labels = ["GIMT", "GIPS", "ADMIN", "LEAVE", "EXEMPTED"]
    dfs = stepwise_file_upload(labels, key_prefix="demo")

    # Once all are uploaded
    if len(dfs) == len(labels):
        st.success("✅ All five files uploaded successfully!")

        df_splits = {}

        for label in labels:
            df_raw = dfs.get(label)
            if df_raw is not None:
                try:
                    if label in ["GIMT", "GIPS", "ADMIN"]:
                        # Split only for first 3
                        df_all, df_in, df_out = split_file(df_raw)
                        df_splits[label] = {
                            "all": df_all,
                            "in": df_in,
                            "out": df_out,
                        }
                        st.write(f"✔️ {label} Split Done")
                        st.dataframe(df_all.head(2))
                    else:
                        # Keep raw for LEAVE + EXEMPTED
                        df_splits[label] = {"raw": df_raw}
                        st.write(f"✔️ {label} Uploaded (raw only)")
                        st.dataframe(df_raw.head(2))

                except Exception as e:
                    st.error(f"⚠️ Failed processing {label}: {e}")

        # Store in session_state
        st.session_state["attendance_splits"] = df_splits


if __name__ == "__main__":
    main()

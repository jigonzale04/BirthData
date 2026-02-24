import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("Provisional Natality Data Dashboard")
st.subheader("Birth Analysis by State and Gender")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _key(c: str) -> str:
    return "".join(ch for ch in str(c).lower() if ch.isalnum())


def _match_required_columns(df: pd.DataFrame, required: list[str]) -> tuple[dict[str, str], list[str]]:
    cols = list(df.columns)
    col_key_map = {_key(c): c for c in cols}

    mapping: dict[str, str] = {}
    missing: list[str] = []

    for req in required:
        if req in cols:
            mapping[req] = req
            continue
        rk = _key(req)
        if rk in col_key_map:
            mapping[req] = col_key_map[rk]
        else:
            missing.append(req)

    return mapping, missing


@st.cache_data(show_spinner=False)
def _load_data() -> pd.DataFrame | None:
    try:
        df0 = pd.read_csv("Provisional_Natality_2025_CDC.csv")
        return df0
    except FileNotFoundError:
        try:
            df0 = pd.read_csv("/mnt/data/Provisional_Natality_2025_CDC.csv")
            return df0
        except FileNotFoundError:
            return None
    except Exception:
        return None


df_raw = _load_data()
if df_raw is None:
    st.error("Dataset file not found in repository.")
    st.stop()

df = _normalize_columns(df_raw)

required_logical = [
    "state_of_residence",
    "month",
    "month_code",
    "year_code",
    "sex_of_infant",
    "births",
]

col_map, missing = _match_required_columns(df, required_logical)
if missing:
    st.error(
        "Required column(s) missing after normalization: "
        + ", ".join(missing)
        + ". Please verify the dataset schema."
    )
    st.write(df.columns)
    st.stop()

# Work with canonical column names without modifying original df
canonical = {}
for logical_name, actual_col in col_map.items():
    canonical[logical_name] = actual_col

df_work = df.copy()
df_work[canonical["births"]] = pd.to_numeric(df_work[canonical["births"]], errors="coerce")
df_work = df_work.dropna(subset=[canonical["births"]])

# Sidebar filters (multiselect only, with "All")
st.sidebar.header("Filters")

state_col = canonical["state_of_residence"]
month_col = canonical["month"]
month_code_col = canonical["month_code"]
gender_col = canonical["sex_of_infant"]

# Build options dynamically (no hardcoding)
states = (
    df_work[state_col]
    .dropna()
    .astype(str)
    .sort_values()
    .unique()
    .tolist()
)
genders = (
    df_work[gender_col]
    .dropna()
    .astype(str)
    .sort_values()
    .unique()
    .tolist()
)

months_df = df_work[[month_col, month_code_col]].dropna(subset=[month_col]).copy()
months_df[month_col] = months_df[month_col].astype(str)
months_df[month_code_col] = pd.to_numeric(months_df[month_code_col], errors="coerce")

if months_df[month_code_col].notna().any():
    months_ordered = (
        months_df.dropna(subset=[month_code_col])
        .drop_duplicates(subset=[month_col])
        .sort_values(by=[month_code_col, month_col])
    )
    months = months_ordered[month_col].tolist()
else:
    months = months_df[month_col].drop_duplicates().sort_values().tolist()

state_sel = st.sidebar.multiselect(
    "State of Residence",
    options=["All"] + states,
    default=["All"],
)
month_sel = st.sidebar.multiselect(
    "Month",
    options=["All"] + months,
    default=["All"],
)
gender_sel = st.sidebar.multiselect(
    "Gender",
    options=["All"] + genders,
    default=["All"],
)

# Filtering logic (do not modify original dataframe)
filtered = df_work.copy()

if state_sel and "All" not in state_sel:
    filtered = filtered[filtered[state_col].astype(str).isin([str(x) for x in state_sel])]
if month_sel and "All" not in month_sel:
    filtered = filtered[filtered[month_col].astype(str).isin([str(x) for x in month_sel])]
if gender_sel and "All" not in gender_sel:
    filtered = filtered[filtered[gender_col].astype(str).isin([str(x) for x in gender_sel])]

if filtered.empty:
    st.warning("No data matches the selected filters. Try broadening your selections.")
    st.dataframe(filtered.reset_index(drop=True), use_container_width=True, hide_index=True)
    st.stop()

# Aggregation
agg = (
    filtered.groupby([state_col, gender_col], dropna=False)[canonical["births"]]
    .sum()
    .reset_index()
    .rename(columns={canonical["births"]: "births"})
)
agg[state_col] = agg[state_col].astype(str)
agg[gender_col] = agg[gender_col].astype(str)
agg = agg.sort_values(by=[state_col, gender_col])

# Plot
fig = px.bar(
    agg,
    x=state_col,
    y="births",
    color=gender_col,
    title="Total Births by State and Gender",
    template="plotly_white",
)
fig.update_layout(
    legend_title_text="Gender",
    xaxis_title="State of Residence",
    yaxis_title="Births",
    margin=dict(l=20, r=20, t=60, b=20),
)

st.plotly_chart(fig, use_container_width=True)

# Filtered data table (raw filtered rows)
st.subheader("Filtered Records")
st.dataframe(filtered.reset_index(drop=True), use_container_width=True, hide_index=True)

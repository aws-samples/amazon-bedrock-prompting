import streamlit as st
import pandas as pd
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
from datetime import datetime

st.set_page_config(layout="wide", page_icon=":robot:", page_title="Prompt Examples Catalogue")
st.header("Prompt Catalogue Workbench - Browse, create, and import GenAI prompts")

st.markdown(
    """
    <style>
        [data-testid=stSidebar] [data-testid=stImage]{
            text-align: center;
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 80%;
        }
    </style>
    """, unsafe_allow_html=True)
st.sidebar.image('AWS_logo_RGB.png', width=100)
st.sidebar.divider()

default_catalogue = "./aws-examples-07082023.parquet.gzip"

if 'catalogue' not in st.session_state:
    st.session_state['catalogue'] = default_catalogue

def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns
    Args: df (pd.DataFrame): Original dataframe
    Returns: pd.DataFrame: Filtered dataframe
    """
    modify = st.checkbox("Add filters")
    if not modify:
        return df
    df = df.copy()
    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass
        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)
    modification_container = st.container()
    with modification_container:
        to_filter_columns = st.multiselect("Filter dataframe on", df.columns)
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            # Treat columns with < 10 unique values as categorical
            if is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                user_cat_input = right.multiselect(
                    f"Values for {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                )
                df = df[df[column].isin(user_cat_input)]
            elif is_numeric_dtype(df[column]):
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f"Values for {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Substring or regex in {column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]
    return df


def dataframe_with_selections(df):
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Select", False)

    # Get dataframe row-selections from user with st.data_editor
    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=df.columns,
    )

    # Filter the dataframe using the temporary column, then drop the column
    selected_rows = edited_df[edited_df.Select]
    return selected_rows.drop('Select', axis=1)


with st.sidebar:
    st.subheader("")
    current_catalogue = st.empty()
    current_catalogue.text(f"Using Catalogue:\n{st.session_state['catalogue']}")
    st.divider()
    catalogue_options = ["AWS examples (August 2023)", "<Import your own catalogue>", "<Create new catalogue>"]
    catalogue_choice = st.selectbox("Select catalogue option:", catalogue_options)
    if catalogue_options.index(catalogue_choice) == 0:
        ### Using default catalogue
        st.session_state['catalogue'] = default_catalogue
        current_catalogue.text(f"Using Catalogue:\n{st.session_state['catalogue']}")
    if catalogue_options.index(catalogue_choice) == 1:
        ### Importing a catalogue
        st.write("Prompt example catalogues can be imported in compressed [Parquet](https://parquet.apache.org/) format with 'parquet.gzip' extension, having all the required fields as specified in the [README](../README.md).")
        uploaded_file = st.file_uploader("Choose a Parquet file...")
        if uploaded_file is not None:
            dataframe = pd.read_parquet(uploaded_file, engine='pyarrow')
            st.session_state['catalogue'] = uploaded_file.name
            current_catalogue.text(f"Using Catalogue:\n{st.session_state['catalogue']}")
    elif catalogue_options.index(catalogue_choice) == 2:
        ### Creating a new catalogue
        st.markdown("Prompt example catalogues are create in [Parquet](https://parquet.apache.org/) format, having all the required fields as specified in the [README](../README.md).")
        catalogue = st.text_input("Catalogue name")
        if catalogue is not "":
            columns = ["industry", "use case", "task", "prompting technique", "language", "model", "date added", "input prompt", "model output"]
            df = pd.DataFrame([], columns=columns)
            try:
                df.to_parquet(f'{catalogue}.parquet.gzip', compression='gzip')
            except:
                e = RuntimeError('This is an exception of type RuntimeError')
                st.exception(e)
            st.session_state['catalogue'] = f"./{catalogue}.parquet.gzip"
            current_catalogue.text(f"Using Catalogue:\n{st.session_state['catalogue']}")

tab1, tab2 = st.tabs(["Search Prompts", "Add Prompts"])

#### SEARCH IN CURRENT CATALOGUE
with tab1:
    st.subheader("Search in Current Catalogue")
    df = pd.read_parquet(st.session_state['catalogue'], engine='pyarrow')
    selection = dataframe_with_selections(df)
    st.divider()
    if len(selection) == 1:
        for (name, content) in selection.iteritems():
            st.markdown(f"**{name}:**")
            st.markdown(content[content.index[0]])
        delete_me = st.button("Delete Prompt")
        #dummy = st.empty()
        dummy = st.container()
        with dummy:
            if delete_me:
                st.error("Do you want to delete this prompt from the catalogue?")
                delete = st.button("Yes, delete")
                cancel = st.button("No, cancel")
                if delete:
                    ### Delete this row from df somehow... and write to catalogue
                    selection = dataframe_with_selections(df)
                elif cancel:
                    dummy.empty()


#### ADD TO CURRENT CATALOGUE
with tab2:
    st.subheader("Add to Your Catalogue")
    df = pd.read_parquet(st.session_state['catalogue'], engine='pyarrow')
    industry = st.selectbox("Industry/Vertical", [
        "Adevertisement & Marketing",
        "Automotive",
        "Consumer Packaged Goods",
        "Education",
        "Energy",
        "Financial Services",
        "Gaming",
        "Government",
        "Healthcare & Life Sciences",
        "Hospitality",
        "Industrial",
        "Insurance",
        "Manufacturing",
        "Marketplaces",
        "Media & Entertainment",
        "Nonprofit",
        "Power & Utilities",
        "Real Estate"
        "Retail",
        "Semiconductor",
        "Sports",
        "Telecom",
        "Travel",
        "Other"
    ])
    if industry == "Other":
        industry = st.text_input("Please specify:")
    usecase = st.text_area("Brief Use Case Description")
    task = st.selectbox("GenAI Task", [
        "Text Generation",
        "Complex Reasoning",
        "Question Answering & Dialogue Assistants (no memory)",
        "Text Summarization",
        "Text Classification",
        "Code Generation",
        "Other"
    ])
    if usecase == "Other":
        usecase = st.text_input("Please specify:")
    technique = st.selectbox("Prompting Technique", [
        "Zero-shot",
        "Few-shot",
        "Chain of Thoughts (CoT)",
        "Reasoning & Acting (ReAct)",
        "Other"
    ])
    if technique == "Other":
        technique = st.text_input("Please specify:")
    language = st.selectbox("Language",[
        "English",
        "Spanish",
        "Mandarin",
        "French",
        "Portuguese",
        "German",
        "Italian",
        "Hindi",
        "Arabic",
        "Bengali",
        "Other"
    ])
    if language == "Other":
        language = st.text_input("Please specify:")
    model = st.selectbox("Large Language Model (LLM)", [
        "Amazon Titan",
        "Anthropics Claude v1.3",
        "Anthropics Claude v2",
        "Cohere Command",
        "Cohere Embed",
        "AI21 Jurassic-2 Jumbo",
        "AI21 Jurassic-2 Ultra",
        "Other"
    ])
    if model == "Other":
        model = st.text_input("Please specify:")
    prompt = st.text_area("Input Prompt")
    output = st.text_area("LLM Output")

    write = st.button("Add to Catalogue")

    if write:
        date = datetime.now().strftime("%Y%m%d")
        df = df.append(pd.Series([industry, usecase, task, technique, language, model, date, prompt, output], index=df.columns), ignore_index=True)
        st.dataframe(df)
        try:
            df.to_parquet(st.session_state['catalogue'], compression='gzip')
        except:
            e = RuntimeError('This is an exception of type RuntimeError')
            st.exception(e)

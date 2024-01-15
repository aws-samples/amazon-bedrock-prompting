import streamlit as st
from streamlit_chat import message
from langchain.llms.bedrock import Bedrock
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from typing import Dict
import json
from io import StringIO
from random import randint
import boto3
from langchain import PromptTemplate

st.set_page_config(page_title="Autoprompting", page_icon=":robot:", layout="wide")
st.header("Auto-prompting - Create prompts for GenAI easily")
st.image('bedrock.png', width=80)

# BEDROCK
session = boto3.Session(
    service_name='bedrock-runtime',
    region_name='us-east-1'
    #profile_name='bedrock'
)
    
bedrock = session.client(
        service_name='bedrock',
        region_name='us-east-1',
        endpoint_url='https://bedrock.us-east-1.amazonaws.com',
)
    
@st.cache_resource
def load_chain(temperature):
    llm = Bedrock(
        #model_id ='anthropic.claude-instant-v1'
        model_id='anthropic.claude-v1',
        client=bedrock,
        model_kwargs={
            'max_tokens_to_sample':8000,
            'temperature':temperature,
            'top_p':0.9,
            'stop_sequences': ["Human"]
        }
    )
    memory = ConversationBufferMemory()
    chain = ConversationChain(llm=llm, memory=memory)
    return chain
    
# this is the object we will work with in the ap - it contains the LLM info as well as the memory
temperature=0
chatchain = load_chain(temperature)
    
# initialise session variables
if 'generated' not in st.session_state:
    st.session_state['generated'] = []
if 'past' not in st.session_state:
    st.session_state['past'] = []
    chatchain.memory.clear()
if 'widget_key' not in st.session_state:
    st.session_state['widget_key'] = str(randint(1000, 100000000))
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
show_prompt = st.sidebar.checkbox('Show prompt')
input_prompt = ''
clear_button = st.sidebar.button("Clear Conversation", key="clear")
    
st.markdown(
    f'''
        <style>
            .sidebar .sidebar-content {{
                width: 150px;
            }}
        </style>
    ''',
    unsafe_allow_html=True
)
    
if clear_button:
    st.session_state['generated'] = []
    st.session_state['past'] = []
    st.session_state['widget_key'] = str(randint(1000, 100000000))
    chatchain.memory.clear()
    
#Options...
col1, col2 = st.columns(2)
    
with col1:
    role = st.selectbox(
        'This bot should act as a...',
        ('business person', 'data scientist', 'technical expert', 'kid', 'customer service agent', 'other'))
    if role == 'other':
        role = st.text_input('Custom selection:')
    
    contextual_info = st.text_input('Any contextual information for this bot?:')
    
    temp = st.checkbox('Responses should be creative (leave unchecked for factual responses)')
    if temp:
        temperature = 1
    else:
        temperature = 0
        
with col2:
    style = st.selectbox(
        'The style or format of the response should be...',
        ('formal', 'informal', 'simple', 'detailed', 'short', 'long', 'other'))
    if style == 'other':
        style = st.text_input('Custom selection:')
    
    language = st.selectbox(
        'The language of this bot should be...',
        ('english', 'spanish', 'portuguese', 'other'))
    if language == 'other':
        language = st.text_input('Custom selection:')
    
    guardrails = st.text_input('This bot should not respond to the following words or topics...')
    
#--- Process prompt
prompt = PromptTemplate(
    input_variables=["user_input", "role", "style", "language", "contextual_info", "guardrails"], 
    template="""
    Context: {contextual_info}
    Act as a {role}. Provide the answers in a {style} way. Provide the answers in {language}.
    If the Human request includes the words or topics in the <guardrails></guardrails> XML tags, then just respond with the message 'Sorry, but I cannot respond to this.'.
    <guardrails>
    {guardrails}
    </guardrails>
    Human: {user_input}
    Assistant:
    """
)
    
# this is the container that displays the past conversation
response_container = st.container()
# this is the container with the input text box
container = st.container()
    
with container:
    # define the input text box
    with st.form(key='my_form', clear_on_submit=True):
        user_input = st.text_area("You:", key='input', height=50)
        submit_button = st.form_submit_button(label='Send')
    
    # when the submit button is pressed we send the user query to the chatchain object and save the chat history
    if submit_button and user_input:
        input_prompt = prompt.format(
            role=role,
            user_input=user_input,
            style=style,
            language=language,
            contextual_info=contextual_info,
            guardrails=guardrails
        )
        output = chatchain(input_prompt)["response"]
        st.session_state['past'].append(user_input)
        st.session_state['generated'].append(output)
    
# this loop is responsible for displaying the chat history
if st.session_state['generated']:
    with response_container:
        for i in range(len(st.session_state['generated'])):
            message(st.session_state["past"][i], is_user=True, key=str(i) + '_user', avatar_style="adventurer", seed=10)
            message(st.session_state["generated"][i], key=str(i), avatar_style="bottts", seed=123)
    
if show_prompt and input_prompt:
    st.sidebar.write('Prompt:\n' + input_prompt)

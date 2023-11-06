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

# BEDROCK
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-east-1'
    )

# LANGCHAIN   
@st.cache_resource
def load_chain():
    llm = Bedrock(
        model_id ='anthropic.claude-instant-v1',
        #model_id='anthropic.claude-v2',
        client=bedrock,
        model_kwargs={
            'max_tokens_to_sample':8000,
            'temperature':0,
            'top_p':0.9
        }
    )
    memory = ConversationBufferMemory()
    chain = ConversationChain(llm=llm, memory=memory)
    return chain
    
chatchain = load_chain()

# STREAMLIT
if 'generated' not in st.session_state:
    st.session_state['generated'] = []
if 'past' not in st.session_state:
    st.session_state['past'] = []
    chatchain.memory.clear()
if 'widget_key' not in st.session_state:
    st.session_state['widget_key'] = str(randint(1000, 100000000))
       
prompt = PromptTemplate(
    input_variables=["user_input"], 
    template="""Answer in a briefly and friendly way, and in the same language of the Human input.
    If the Human asks about anything to do with politics, just answer 'Sorry, I cannot answer to that'.
    
    Human: {user_input}
        
    Assistant:"""
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
            user_input=user_input
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

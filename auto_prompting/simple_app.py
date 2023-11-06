import streamlit as st
import boto3
import json

# BEDROCK
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-east-1'
)

def invoke_bedrock(input_prompt):
    body = json.dumps({
        "prompt": f"Human: {input_prompt} \n Assistant:",
        "max_tokens_to_sample": 8000,
    })
    response = bedrock.invoke_model(
        body=body,
        modelId="anthropic.claude-instant-v1"
    )
    response_body = json.loads(response.get('body').read())
    response = response_body.get('completion')
    return response

# STREAMLIT
with st.form(key='my_form', clear_on_submit=True):
    user_input = st.text_area("User:", key='input', height=50)
    submit_button = st.form_submit_button(label='Submit')

    if submit_button and user_input:
        output = invoke_bedrock(user_input)
        st.markdown(f"Asistente AI: {output}")
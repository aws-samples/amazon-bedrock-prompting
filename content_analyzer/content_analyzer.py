import json
import boto3
import streamlit as st
import textract
from pypdf import PdfReader

region = 'eu-west-1' ###REPLACE WTIH YOUR OWN AWS REGION
s3_bucket = 'rodzanto2022' ###REPLACE WTIH YOUR OWN AMAZON S3 BUCKET
s3_prefix = 'content-analyzer/content'

if 'img_summary' not in st.session_state:
    st.session_state['img_summary'] = None
if 'csv_summary' not in st.session_state:
    st.session_state['csv_summary'] = None
if 'new_contents' not in st.session_state:
    st.session_state['new_contents'] = None
if 'label_text' not in st.session_state:
    st.session_state['label_text'] = None

s3 = boto3.client(service_name='s3', region_name=region)
comprehend = boto3.client(service_name='comprehend',region_name=region)
rekognition = boto3.client(service_name='rekognition',region_name=region)
boto3_bedrock = boto3.client(service_name='bedrock-runtime',region_name='us-east-1')

p_summary = ''
st.set_page_config(page_title="GenAI Content Analyzer", page_icon="sparkles", layout="wide")

st.markdown("## Analyze any content with Amazon Bedrock")
st.markdown(
    """
    <style>
        [data-testid=stSidebar] [data-testid=stImage]{
            text-align: center;
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 25%;
        }
    </style>
    """, unsafe_allow_html=True
)
st.sidebar.image("./bedrock.png")
st.sidebar.header("GenAI Content Analyzer")
values = [1, 2, 3, 4, 5]
default_ix = values.index(3)
ftypes = ['csv', 'pptx', 'rtf','xls','xlsx','txt', 'pdf', 'doc', 'docx', 'json','ipynb','py','java']
atypes = ['csv', 'pptx', 'rtf','xls','xlsx','txt', 'pdf', 'doc', 'docx', 'json','ipynb','py','java', 'png', 'jpg']
languages = ['English', 'Spanish', 'German', 'Portugese', 'Korean', 'Irish', 'Star Trek - Klingon', 'Star Trek - Ferengi', 'Italian', 'French', 'Japanese', 'Mandarin', 'Tamil', 'Hindi', 'Telugu', 'Kannada', 'Arabic', 'Hebrew']
p_count = st.sidebar.selectbox('Select the count of auto-prompt suggestions to generate...', values, index=default_ix)
model = 'Anthropic Claude'

def call_anthropic(query):
    prompt_data = f"""Human: {query}
    Assistant:"""
    body = json.dumps({
        "prompt": prompt_data,
        "max_tokens_to_sample":8000,
        "temperature":0,
        "top_p":0.9
    })
    modelId = 'anthropic.claude-v2'
    #modelId = 'anthropic.claude-instant-v1'
    print(body)
    response = boto3_bedrock.invoke_model(body=body, modelId=modelId)
    response_body = json.loads(response.get('body').read())
    outputText = response_body.get('completion')
    return outputText

def readpdf(filename):
    reader = PdfReader(filename)
    raw_text = []
    for page in reader.pages:
        raw_text.append(page.extract_text())
    return '\n'.join(raw_text)

def GetAnswers(original_text, query):
    if query == "cancel":
        answer = 'It was swell chatting with you. Goodbye for now'
    else:
        generated_text = ''
        if model.lower() == 'anthropic claude':  
            generated_text = call_anthropic(original_text+'. Answer from this text with no hallucinations, false claims or illogical statements: '+ query.strip("query:"))
            if generated_text != '':
                answer = str(generated_text)+' '
            else:
                answer = 'Claude did not find an answer to your question, please try again'   
    return answer          

def upload_image_detect_labels(bytes_data):
    summary = ''
    label_text = ''
    response = rekognition.detect_labels(
        Image={'Bytes': bytes_data},
        Features=['GENERAL_LABELS']
    )
    text_res = rekognition.detect_text(
        Image={'Bytes': bytes_data}
    )
    for text in text_res['TextDetections']:
        label_text += text['DetectedText'] + ' '
    for label in response['Labels']:
        label_text += label['Name'] + ' '
    st.session_state.label_text = label_text
    if model.lower() == 'anthropic claude':  
        generated_text = call_anthropic('Explain the contents of this image in 300 words from these labels in ' +language+ ': '+ label_text)
        if generated_text != '':
            generated_text.replace("$","USD")
            summary = str(generated_text)+' '
        else:
            summary = 'Claude did not find an answer to your question, please try again'    
        return summary    

def upload_csv_get_summary(file_type, s3_file_name):
    summary = ''
    s3.download_file(s3_bucket, s3_prefix+'/'+s3_file_name, s3_file_name)
    if file_type not in ['py','java','ipynb','pdf']:
        contents = textract.process(s3_file_name).decode('utf-8')
        new_contents = contents[:50000].replace('$','\$')
    elif file_type == 'pdf':
        contents = readpdf(s3_file_name)
        new_contents = contents[:50000].replace("$","\$")
    else:
        with open(s3_file_name, 'rb') as f:
            contents = f.read()
        new_contents = contents[:50000].decode('utf-8')
    if model.lower() == 'anthropic claude':  
        generated_text = call_anthropic('Create a 300 words summary of this document in ' +language+ ': '+ new_contents)
        if generated_text != '':
            summary = str(generated_text)+' '
            summary = summary.replace("$","\$")
        else:
            summary = 'Claude did not find an answer to your question, please try again'    
    return new_contents, summary    

c1, c2 = st.columns(2)
c1.subheader("Upload your file")
uploaded_img = c1.file_uploader("**Select a file**", type=atypes)
default_lang_ix = languages.index('English')
c2.subheader("Select an output language")
language = c2.selectbox(
    'Bedrock should answer in...',
    options=languages, index=default_lang_ix)
img_summary = ''
csv_summary = ''
file_type = ''
new_contents = ''

if uploaded_img is not None:
    if 'jpg' in uploaded_img.name or 'png' in uploaded_img.name or 'jpeg' in uploaded_img.name:
        file_type = 'image'        
        c1.success(uploaded_img.name + ' is ready for upload')
        if c1.button('Upload'):
            with st.spinner('Uploading image file and starting summarization with Amazon Rekognition label detection & Amazon Bedrock...'):
                img_summary = upload_image_detect_labels(uploaded_img.getvalue())
                img_summary = img_summary.replace("$","\$")
                if len(img_summary) > 5:
                    st.session_state['img_summary'] = img_summary
                st.success('File uploaded and summary generated')
    elif str(uploaded_img.name).split('.')[1] in ftypes:
        file_type = str(uploaded_img.name).split('.')[1]            
        c1.success(uploaded_img.name + ' is ready for upload')
        if c1.button('Upload'):
            with st.spinner('Uploading file and starting summarization...'):
                s3.upload_fileobj(uploaded_img, s3_bucket, s3_prefix+'/'+uploaded_img.name)
                new_contents, csv_summary = upload_csv_get_summary(file_type, uploaded_img.name)
                csv_summary = csv_summary.replace("$","\$")
                if len(csv_summary) > 5:
                    st.session_state['csv_summary'] = csv_summary
                new_contents = new_contents.replace("$","\$")
                st.session_state.new_contents = new_contents
                st.success('File uploaded and summary generated')
    else:
        st.write('Incorrect file type provided. Please check and try again')

h_results = ''
p1 = ''
m_summary = ''

if uploaded_img is not None:
    if st.session_state.img_summary:
        if len(st.session_state.img_summary) > 5:
            st.image(uploaded_img)
            st.markdown('**Image summary**: \n')
            st.write(str(st.session_state['img_summary']))
            if model.lower() == 'anthropic claude':  
                p_text = call_anthropic('Generate'+str(p_count)+'prompts with use cases ideas to query the summary: '+ st.session_state.img_summary)
                p_text1 = []
                p_text2 = ''
                if p_text != '':
                    p_text.replace("$","\$")
                    p_text1 = p_text.split('\n')
                    for i,t in enumerate(p_text1):
                        if i > 1:
                            p_text2 += t.split('\n')[0]+'\n\n'
                    p_summary = p_text2
            st.sidebar.markdown('### Suggested auto-prompts \n\n' + p_summary)
    elif st.session_state.csv_summary:
        if len(st.session_state.csv_summary) > 5:
            st.markdown('**Summary**: \n')
            st.write(str(st.session_state.csv_summary).replace("$","\$"))
            if model.lower() == 'anthropic claude':
                p_text = call_anthropic('Generate'+str(p_count)+'prompts with use cases ideas to query the text: '+ st.session_state.csv_summary)
                p_text1 = []
                p_text2 = ''
                if p_text != '':
                    p_text.replace("$","\$")
                    p_text1 = p_text.split('\n')
                    for i,t in enumerate(p_text1):
                        if i > 1:
                            p_text2 += t.split('\n')[0]+'\n\n'
                    p_summary = p_text2
            st.sidebar.markdown('### Suggested auto-prompts \n\n' + p_summary)

input_text = st.text_input('**Type your question or instruction:**', key='text')
if input_text != '':
    if st.session_state.img_summary:
        result = GetAnswers(st.session_state.img_summary,input_text)
        result = result.replace("$","\$")
        st.write(result)
    elif st.session_state.csv_summary:
        s3.download_file(s3_bucket, s3_prefix+'/'+uploaded_img.name, uploaded_img.name)
        if file_type not in ['py','java','ipynb','pdf']:
            contents = textract.process(uploaded_img.name).decode('utf-8')
            new_contents = contents[:50000].replace('$','\$')
        elif file_type == 'pdf':
            contents = readpdf(uploaded_img.name)
            new_contents = contents[:50000].replace("$","\$")
        else:
            with open(uploaded_img.name, 'rb') as f:
                contents = f.read()
            new_contents = contents[:50000].decode('utf-8')
        lang = comprehend.detect_dominant_language(Text=new_contents)
        lang_code = str(lang['Languages'][0]['LanguageCode']).split('-')[0]
        if lang_code in ['en']:
            resp_pii = comprehend.detect_pii_entities(Text=new_contents, LanguageCode=lang_code)
            immut_summary = new_contents
            for pii in resp_pii['Entities']:
                if pii['Type'] not in ['NAME', 'AGE', 'ADDRESS','DATE_TIME']:
                    pii_value = immut_summary[pii['BeginOffset']:pii['EndOffset']]
                    new_contents = new_contents.replace(pii_value, str('PII - '+pii['Type']))
        result = GetAnswers(new_contents,input_text)
        result = result.replace("$","\$")
        st.write(result)
    else:
        st.write("I am sorry it appears you have not uploaded any files for analysis. Can you please upload a file and then try again?")

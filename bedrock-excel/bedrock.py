import boto3, json
import xlwings as xw
import time

book = xw.Book.caller()

def get_bedrock():
    sheet0 = book.sheets[0] #Pre-requisites sheet

    #Get spreadsheet config values...
    profile_name = sheet0["C16"].value or 'default'
    assumed_role = sheet0["C20"].value
    region_name = sheet0["C24"].value or 'us-east-1'
    endpoint_url = sheet0["C25"].value or f'https://bedrock-runtime.{region_name}.amazonaws.com'
    #For internal Isengard accounts in preview use: endpoint_url = 'https://prod.us-west-2.frontend.bedrock.aws.dev'

    client_kwargs = {}
    if assumed_role:
        session = boto3.Session()
        sts = session.client("sts")
        response = sts.assume_role(
            RoleArn=str(assumed_role),
            RoleSessionName="bedrock-excel"
        )
        client_kwargs["aws_access_key_id"] = response["Credentials"]["AccessKeyId"]
        client_kwargs["aws_secret_access_key"] = response["Credentials"]["SecretAccessKey"]
        client_kwargs["aws_session_token"] = response["Credentials"]["SessionToken"]
    else:
        session = boto3.Session(profile_name=profile_name)


    bedrock = session.client(
        service_name='bedrock-runtime',
        region_name=region_name,
        endpoint_url=endpoint_url,
        **client_kwargs
    )


    return bedrock

def test_bedrock():
    sheet0 = book.sheets[0] #Pre-requisites sheet
    bedrock = get_bedrock()
    body = json.dumps({
        "prompt": """Human: Just answer with the text 'Hello from Bedrock'
        Assistant:
        """,
        "max_tokens_to_sample":100
    })

    response = bedrock.invoke_model(body=body, modelId='anthropic.claude-instant-v1')
    response = json.loads(response.get('body').read())
    response = response.get('completion')

    sheet0["C34"].value = response


def call_bedrock(row):
    bedrock = get_bedrock()
    sheet1 = book.sheets[1] #Call Bedrock sheet

    #Get prompt parameters and input...
    prompt = sheet1[f"B{row}"].value
    
    max_tokens_to_sample = sheet1["C8"].value or 8000
    temperature = sheet1["C6"].value or 0
    top_p = sheet1["C7"].value or 0.9
    modelId = sheet1["C5"].value or 'anthropic.claude-instant-v1'
    report_time = sheet1["C9"].value or False

    body = json.dumps({
        "prompt": str(prompt),
        "max_tokens_to_sample": int(max_tokens_to_sample),
        "temperature": int(temperature),
        "top_p": top_p
    })

    start_time = time.time()
    try:
        response = bedrock.invoke_model(body=body, modelId=modelId)
        response = json.loads(response.get('body').read())
        response = response.get('completion')
    except:
        response = "ERROR: Something went wrong"
        
    response_time = (time.time() - start_time)

    sheet1[f"C{row}"].value = response
    if report_time:
        sheet1[f"D{row}"].value = round(response_time, 2)


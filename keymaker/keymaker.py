import langchain
import os
import sys
import pathlib

def help():
    print("keymaker v1 - Prompt translation across LLMs made easy")
    print("Commands: help, show_templates, translate\n")
    print("show_templates:\nTo check available templates just run: show_templates()\n")
    print("translate:\nYou must provide:\n1. A user input (mandatory)\n2. At least one valid model (mandatory)\n3. A context (optional).\nSyntax: translate(user_input_text, models_list, context_text)\n")
    return

def show_templates():
    templates=[]
    file_path = pathlib.Path('./templates/')
    templates = list(file_path.rglob('*.txt'))
    for i,j in enumerate(templates):
        templates[i] = str(j).split("/")[1] + "/" + str(j).split("/")[2]
        templates[i] = templates[i].split(".txt")[0]
    return templates

def translate(user_input, models, context="", task="qa"):
    prompt_template = ""
    prompts=[]

    if not models or not user_input:
        help()
        sys.exit(0)

    for i in models:
        if not os.path.isfile(f'./templates/{i}/{task}.txt'):
            print(f"The model '{i}' & task '{task}' combination does not exist in the library. To check available templates run: show_templates")
            sys.exit(0)

        with open(f'./templates/{i}/{task}.txt') as f:
            template = f.read()
        template = template.strip()

        from langchain.prompts import PromptTemplate

        prompt_template = PromptTemplate(
            input_variables=["query", "context"],
            template=template
        )

        prompts.append(prompt_template.format(query=user_input, context=context))

    return prompts


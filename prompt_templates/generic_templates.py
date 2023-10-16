from langchain import PromptTemplate

def claude_generic(input_prompt):
    prompt = PromptTemplate.from_template("""Human: {input_prompt}
    
    Assistant:
    """)
    return prompt

def titan_generic(input_prompt):
    prompt = PromptTemplate.from_template("""User: {input_prompt}
    
    Assistant:
    """)
    return prompt

def llama2_generic(input_prompt, system_prompt):
    prompt = PromptTemplate.from_template("""<s>[INST] <<SYS>>
    {system_prompt}
    <</SYS>>

    {input_prompt} [/INST]
    """)
    return prompt
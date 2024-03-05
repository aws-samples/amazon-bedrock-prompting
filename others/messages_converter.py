#Simple prompt converter from Anthropic Claude Text Completions API to Messages API
#for details check the documentation here: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html

import json, sys

input_prompt = (sys.argv[1]).replace('//', '/')

if input_prompt:
    system_prompt = input_prompt.split("Human:")[0]
    nosystem_prompt = input_prompt.split("Human:")[1]
    user_prompt = nosystem_prompt.split("Assistant:")[0]
    assistant_prompt = nosystem_prompt.split("Assistant:")[1]

    output_prompt = []

    if user_prompt:
        output_prompt.append({"role": "user", "content": user_prompt})
    
    if assistant_prompt:
        output_prompt.append({"role": "assistant", "content": assistant_prompt})

    print(f'\nSystem prompt (for the "system" parameter):\n"{system_prompt}"\n\nMessages prompts (for the "messages" parameter):\n"{json.dumps(output_prompt, ensure_ascii=False)}"')
    print('\nFor more info check the documentation here: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html')

else:
    raise ValueError("Please pass an input prompt between double quotes as the argument.")
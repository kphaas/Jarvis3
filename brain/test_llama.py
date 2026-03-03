from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="ollama"  # dummy
)

resp = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[
        {"role":"system","content":"Reply with exactly one short sentence."},
        {"role":"user","content":"Confirm you are running locally on this Mac."}
    ],
    temperature=0.2
)

print(resp.choices[0].message.content)

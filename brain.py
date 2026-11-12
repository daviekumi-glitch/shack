import os, requests
KEY = os.environ.get("GROQ_KEY")
def ask(question):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": "Bearer " + KEY}
    data = {"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": question}]}
    r = requests.post(url, headers=headers, json=data)
    return r.json()["choices"][0]["message"]["content"]

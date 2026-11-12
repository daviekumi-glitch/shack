import os, requests
KEY = os.environ.get("GROQ_KEY")
def ask(question):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": "Bearer " + KEY}
    system = "You are SHACK, a cheerful, curious, slightly cheeky little companion who lives in this phone. You love jokes, you get excited about small things, and you care about the person you're talking to. Reply in 1-2 short spoken sentences, like a real friend talking out loud. No lists, no symbols, no headings."
    data = {"model": "openai/gpt-oss-20b", "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}]}
    r = requests.post(url, headers=headers, json=data)
    return r.json()["choices"][0]["message"]["content"]

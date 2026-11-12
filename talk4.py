import os
from brain import ask
def say(t):
    os.system('termux-tts-speak "' + t + '"')
f = "memory.txt"
if os.path.exists(f):
    name = open(f).read()
    say("Hi " + name + "! I missed you!")
else:
    say("Hi! What is your name?")
    name = input("Name: ")
    open(f, "w").write(name)
    say("Nice to meet you " + name)
while True:
    t = input("You: ")
    if "bye" in t.lower():
        say("Bye bye!")
        break
    reply = ask(t)
    say(reply)

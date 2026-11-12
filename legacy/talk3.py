import os
import random
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
jokes = ["Why did the phone go to school? To get smarter!", "Why was the robot hungry? It needed more bytes!", "What do you call a sleepy app? A nap-plication!"]
while True:
    t = input("You: ").lower()
    if "bye" in t:
        say("Bye bye!")
        break
    elif "joke" in t:
        say(random.choice(jokes))
    else:
        say("You said " + t)

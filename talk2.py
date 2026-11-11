import os
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


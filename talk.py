import os
def say(t):
    os.system('termux-tts-speak "' + t + '"')
say("Hi! I missed you!")
while True:
    t = input("You: ").lower()
    if "bye" in t:
        say("Bye bye!")
        break
    say("You said " + t)


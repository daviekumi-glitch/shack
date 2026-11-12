import os, subprocess, random
from brain import ask
def say(t):
    subprocess.run(["termux-tts-speak", t])
f = "memory.txt"
if os.path.exists(f):
    name = open(f).read()
    say("Hi " + name + "! I missed you!")
else:
    say("Hi! What is your name?")
    name = input("Name: ")
    open(f, "w").write(name)
    say("Nice to meet you " + name)
things = ["a banana", "a shoe", "a cloud", "a guitar", "a penguin", "a pizza", "a robot"]
game_on = False
secret = ""
count = 0
while True:
    t = input("You: ")
    low = t.lower()
    if "bye" in low:
        say("Bye bye!")
        break
    elif "play a game" in low or "twenty questions" in low:
        game_on = True
        secret = random.choice(things)
        count = 0
        say("Yay! I am thinking of something. Ask me yes or no questions to guess it!")
    elif game_on:
        count = count + 1
        prompt = "The secret thing is " + secret + ". The player asked: " + t + ". Answer only yes, no, or maybe, in one short sentence, and if they guessed it exactly say they got it right."
        reply = ask(prompt)
        say(reply)
        if count >= 20:
            say("That is 20 questions! The answer was " + secret)
            game_on = False
    else:
        reply = ask(t)
        say(reply)

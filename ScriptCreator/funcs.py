import random

def randomize_time(min, max):
    return random.randint(int(min * 1000), int(max * 1000)) / 1000
import random
import string


def random_string(size=10):
    random_string = ''
    if size < 3 or size > 32:
        return random_string
    char_range = string.ascii_letters
    char_range += string.digits

    for char in range(size):
        random_string += random.choice(char_range)
    return random_string
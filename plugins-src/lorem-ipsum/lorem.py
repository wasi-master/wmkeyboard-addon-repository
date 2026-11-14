# Lorem Ipsum's text: words, sentences and paragraphs of the classic filler.
# Pure functions, so test.py checks them on any Python.

import random

# The vocabulary of the classic filler, which comes from Cicero's
# "De finibus bonorum et malorum" (45 BC) by way of a 1500s typesetter.
WORDS = (
    "a ac accumsan adipiscing aenean aliquam aliquet amet ante arcu at auctor "
    "augue bibendum blandit commodo condimentum congue consectetur consequat "
    "convallis cras cursus dapibus diam dictum dignissim dolor donec dui duis "
    "egestas eget eleifend elementum elit enim erat eros est et etiam eu euismod "
    "facilisis faucibus felis fermentum feugiat fringilla fusce gravida habitant "
    "hendrerit iaculis id imperdiet in integer interdum ipsum justo lacinia lacus "
    "laoreet lectus leo libero ligula lobortis lorem luctus maecenas magna "
    "malesuada massa mattis mauris metus mi molestie mollis morbi nam nec neque "
    "nibh nisi nisl non nulla nullam nunc odio orci ornare pellentesque pharetra "
    "phasellus placerat porta porttitor posuere praesent pretium proin pulvinar "
    "purus quam quis quisque rhoncus risus rutrum sagittis sapien scelerisque sed "
    "sem semper sit sodales sollicitudin suscipit suspendisse tellus tempor "
    "tempus tincidunt tortor tristique turpis ultrices ultricies urna ut varius "
    "vehicula vel velit venenatis vestibulum vitae vivamus viverra volutpat "
    "vulputate"
).split()

OPENING = "Lorem ipsum dolor sit amet, consectetur adipiscing elit"

# One text block on the keyboard holds 2048 characters, so a longer result is
# cut back to the last whole sentence (or word) that fits.
MOST_CHARACTERS = 2048


def capital(word):
    return word[0].upper() + word[1:]


def some_words(n):
    return [random.choice(WORDS) for _ in range(n)]


def sentence():
    """6 to 14 words, maybe with a comma, capitalised, ending in a full stop."""
    words = some_words(random.randint(6, 14))
    if len(words) > 7 and random.random() < 0.5:
        at = random.randint(3, len(words) - 4)
        words[at] = words[at] + ","
    return capital(" ".join(words)) + "."


def paragraph(size):
    return " ".join([sentence() for _ in range(size)])


def generate(unit, n, classic):
    """[n] words, sentences or paragraphs; [classic] opens with the famous line."""
    if unit == "words":
        words = some_words(n)
        if classic:
            opening = OPENING.replace(",", "").lower().split()
            words = (opening + words)[:n]
        text = " ".join(words)
        return capital(text) if classic else text

    if unit == "sentences":
        parts = [sentence() for _ in range(n)]
        if classic:
            parts[0] = OPENING + "."
        return " ".join(parts)

    parts = [paragraph(random.randint(4, 7)) for _ in range(n)]
    if classic:
        parts[0] = OPENING + ". " + parts[0]
    return "\n\n".join(parts)


def fit(text):
    """The text, cut to MOST_CHARACTERS at a sentence end, or a word end."""
    if len(text) <= MOST_CHARACTERS:
        return text
    head = text[:MOST_CHARACTERS]
    end = head.rfind(".")
    if end > 0:
        return head[:end + 1]
    return head[:head.rfind(" ")]


def count_of(typed, most):
    """What a typed count means: a whole number from 1 to [most], or None."""
    digits = "".join([c for c in str(typed) if c.isdigit()])
    if not digits:
        return None
    return max(1, min(most, int(digits)))

# Tests for Lorem Ipsum's text, run by tools/test_plugins.py. The text is
# random, so these check its shape: how many words, sentences and paragraphs,
# how it starts, that it fits, and what a typed count means.

import lorem

fails = []


def expect(what, ok, detail=""):
    if not ok:
        fails.append(what + (": " + str(detail) if detail else ""))


for n in (1, 7, 15, 50):
    words = lorem.generate("words", n, True).split()
    expect(str(n) + " words", len(words) == n, len(words))
expect("classic opening", lorem.generate("words", 5, True) == "Lorem ipsum dolor sit amet")

text = lorem.generate("sentences", 4, True)
expect("four sentences", text.count(".") == 4, text)
expect("sentences open classic", text.startswith(lorem.OPENING + "."), text[:60])

text = lorem.generate("paragraphs", 3, False)
expect("three paragraphs", len(text.split("\n\n")) == 3)

long = lorem.generate("paragraphs", 10, True)
cut = lorem.fit(long)
expect("fits one block", len(cut) <= lorem.MOST_CHARACTERS, len(cut))
expect("cut at a sentence end", cut.endswith("."), cut[-20:])

expect("typed 15", lorem.count_of("15", 400) == 15)
expect("typed past the most", lorem.count_of("9999", 400) == 400)
expect("typed zero is one", lorem.count_of("0", 400) == 1)
expect("typed nothing", lorem.count_of("", 400) is None)
expect("typed junk", lorem.count_of("abc", 400) is None)

if fails:
    raise SystemExit("\n".join(fails))
print("lorem-ipsum: ok")

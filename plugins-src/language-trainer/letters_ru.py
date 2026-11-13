# Russian Cyrillic, with a learner's romanization (й as j, ы as y).
# "glyph romanization | name". Hand-written for this plugin (MIT).

TITLE = "Cyrillic"
CASED = True

CATEGORIES = [
    ("vowels", "Vowels", """
а a
е ye | ye, e after a consonant
ё yo
и i
о o
у u
ы y | a hard i
э e
ю yu
я ya
"""),
    ("consonants", "Consonants", """
б b
в v
г g
д d
ж zh
з z
й j | short i, as y in boy
к k
л l
м m
н n
п p
р r
с s
т t
ф f
х kh
ц ts
ч ch
ш sh
щ shch
"""),
    ("signs", "Signs", """
ъ hard sign | keeps the sounds apart
ь soft sign | softens the consonant before it
"""),
]

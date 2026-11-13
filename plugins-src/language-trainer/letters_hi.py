# Hindi in Devanagari, with a learner's romanization: long vowels with a
# macron, retroflex consonants with a dot under. "glyph romanization | name".
# Nukta letters are written as letter + nukta (U+093C), the form keyboards
# type. Hand-written for this plugin (MIT).

TITLE = "Devanagari"
CASED = False

CATEGORIES = [
    ("vowels", "Vowels", """
अ a
आ ā
इ i
ई ī
उ u
ऊ ū
ऋ ri
ए e
ऐ ai
ओ o
औ au
अं aṁ | anusvar, a nasal
अः aḥ | visarg, a breath
"""),
    ("consonants", "Consonants", """
क ka
ख kha
ग ga
घ gha
ङ ṅa
च cha
छ chha
ज ja
झ jha
ञ ña
ट ṭa | tongue curled back
ठ ṭha
ड ḍa
ढ ḍha
ण ṇa
त ta | tongue on the teeth
थ tha
द da
ध dha
न na
प pa
फ pha
ब ba
भ bha
म ma
य ya
र ra
ल la
व va
श sha
ष ṣha
स sa
ह ha
"""),
    ("nukta", "Nukta letters", """
क़ qa
ख़ xa | kh from the throat
ग़ ġa
ज़ za
ड़ ṛa
ढ़ ṛha
फ़ fa
"""),
    ("matras", "Vowel signs", """
का kā
कि ki
की kī
कु ku
कू kū
कृ kri
के ke
कै kai
को ko
कौ kau
कं kaṁ
कः kaḥ
"""),
    ("conjuncts", "Joined consonants", """
क्ष kṣha
त्र tra
ज्ञ gya
श्र shra
प्र pra
क्र kra
स्त sta
द्ध ddha
द्व dva
न्त nta
"""),
]

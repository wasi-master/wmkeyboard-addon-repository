# Thai, with the sound each consonant makes at the start of a syllable
# (Royal Thai General System) and its name, which carries its class: mid,
# high or low. Vowels and tones are shown on ก. "glyph romanization | name".
# Hand-written for this plugin (MIT).

TITLE = "Thai script"
CASED = False

CATEGORIES = [
    ("mid", "Mid-class consonants", """
ก k | ko kai
จ ch | cho chan
ฎ d | do chada
ฏ t | to patak
ด d | do dek
ต t | to tao
บ b | bo baimai
ป p | po pla
อ ʔ | o ang, carries vowels
"""),
    ("high", "High-class consonants", """
ข kh | kho khai
ฃ kh | kho khuat, no longer used
ฉ ch | cho ching
ฐ th | tho than
ถ th | tho thung
ผ ph | pho phueng
ฝ f | fo fa
ศ s | so sala
ษ s | so ruesi
ส s | so suea
ห h | ho hip
"""),
    ("low", "Low-class consonants", """
ค kh | kho khwai
ฅ kh | kho khon, no longer used
ฆ kh | kho rakhang
ง ng | ngo ngu
ช ch | cho chang
ซ s | so so
ฌ ch | cho choe
ญ y | yo ying
ฑ th | tho nangmontho
ฒ th | tho phuthao
ณ n | no nen
ท th | tho thahan
ธ th | tho thong
น n | no nu
พ ph | pho phan
ฟ f | fo fan
ภ ph | pho samphao
ม m | mo ma
ย y | yo yak
ร r | ro ruea
ล l | lo ling
ว w | wo waen
ฬ l | lo chula
ฮ h | ho nokhuk
"""),
    ("vowels", "Vowels", """
กะ ka | short a
กา kaa | long a
กิ ki | short i
กี kii | long i
กึ kue | short ue
กือ kuue | long ue
กุ ku | short u
กู kuu | long u
เกะ ke | short e
เก kee | long e
แกะ kae | short ae
แก kaae | long ae
โกะ ko | short o
โก koo | long o
เกาะ kaw | short aw
กอ kaaw | long aw
เกอ koe | long oe
ไก kai | mai malai
ใก kai | mai muan
เกา kao
กำ kam
"""),
    ("tones", "Tone marks", """
กา kaa | no mark, mid tone
ก่า kàa | mai ek, low tone
ก้า kâa | mai tho, falling tone
ก๊า káa | mai tri, high tone
ก๋า kǎa | mai chattawa, rising tone
"""),
]

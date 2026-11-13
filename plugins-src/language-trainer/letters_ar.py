# Arabic, with a scholarly romanization (dots under the emphatic letters,
# ʿ for ʿayn, ʾ for hamza) and each letter's name. "glyph romanization |
# name". Hand-written for this plugin (MIT).

TITLE = "Arabic alphabet"
CASED = False

CATEGORIES = [
    ("letters", "Letters", """
ا ā | ʾalif
ب b | bāʾ
ت t | tāʾ
ث th | thāʾ, th as in thin
ج j | jīm
ح ḥ | ḥāʾ, a breathy h from the throat
خ kh | khāʾ
د d | dāl
ذ dh | dhāl, th as in this
ر r | rāʾ
ز z | zāy
س s | sīn
ش sh | shīn
ص ṣ | ṣād, a heavy s
ض ḍ | ḍād, a heavy d
ط ṭ | ṭāʾ, a heavy t
ظ ẓ | ẓāʾ, a heavy dh
ع ʿ | ʿayn, from the throat
غ gh | ghayn
ف f | fāʾ
ق q | qāf
ك k | kāf
ل l | lām
م m | mīm
ن n | nūn
ه h | hāʾ
و w | wāw, also ū
ي y | yāʾ, also ī
"""),
    ("more", "More letters", """
ء ʾ | hamza, a catch in the throat
أ ʾa | hamza on ʾalif
إ ʾi | hamza under ʾalif
آ ʾā | ʾalif madda
ة a | tāʾ marbūṭa, at the end of a word
ى ā | ʾalif maqṣūra, at the end of a word
لا lā | lām and ʾalif together
"""),
    ("shapes", "Joined shapes", """
بـ b · start
ـبـ b · middle
ـب b · end
جـ j · start
ـجـ j · middle
ـج j · end
عـ ʿ · start
ـعـ ʿ · middle
ـع ʿ · end
هـ h · start
ـهـ h · middle
ـه h · end
كـ k · start
ـكـ k · middle
ـك k · end
يـ y · start
ـيـ y · middle
ـي y · end
"""),
    ("harakat", "Vowel marks", """
بَ ba | fatḥa
بِ bi | kasra
بُ bu | ḍamma
بْ b | sukūn, no vowel
بّ bb | shadda, doubled
بً ban | tanwīn fatḥ
بٍ bin | tanwīn kasr
بٌ bun | tanwīn ḍamm
بَا bā | long a
بِي bī | long i
بُو bū | long u
"""),
]

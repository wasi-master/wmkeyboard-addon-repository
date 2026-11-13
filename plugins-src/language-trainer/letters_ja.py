# Japanese kana with Hepburn romanization. Each line of a table is
# "glyph romanization", then " | a note" where one helps tell letters apart.
# Hand-written for this plugin (MIT); the facts are Unicode's and Hepburn's.

TITLE = "Kana"
CASED = False

CATEGORIES = [
    ("hira", "Hiragana", """
あ a
い i
う u
え e
お o
か ka
き ki
く ku
け ke
こ ko
さ sa
し shi
す su
せ se
そ so
た ta
ち chi
つ tsu
て te
と to
な na
に ni
ぬ nu
ね ne
の no
は ha
ひ hi
ふ fu
へ he
ほ ho
ま ma
み mi
む mu
め me
も mo
や ya
ゆ yu
よ yo
ら ra
り ri
る ru
れ re
ろ ro
わ wa
を wo | said o, written for the object
ん n
"""),
    ("hira_marks", "Hiragana: dakuten", """
が ga
ぎ gi
ぐ gu
げ ge
ご go
ざ za
じ ji | from し
ず zu | from す
ぜ ze
ぞ zo
だ da
ぢ ji | from ち
づ zu | from つ
で de
ど do
ば ba
び bi
ぶ bu
べ be
ぼ bo
ぱ pa
ぴ pi
ぷ pu
ぺ pe
ぽ po
"""),
    ("hira_yoon", "Hiragana: yōon", """
きゃ kya
きゅ kyu
きょ kyo
しゃ sha
しゅ shu
しょ sho
ちゃ cha
ちゅ chu
ちょ cho
にゃ nya
にゅ nyu
にょ nyo
ひゃ hya
ひゅ hyu
ひょ hyo
みゃ mya
みゅ myu
みょ myo
りゃ rya
りゅ ryu
りょ ryo
ぎゃ gya
ぎゅ gyu
ぎょ gyo
じゃ ja
じゅ ju
じょ jo
びゃ bya
びゅ byu
びょ byo
ぴゃ pya
ぴゅ pyu
ぴょ pyo
"""),
    ("kata", "Katakana", """
ア a
イ i
ウ u
エ e
オ o
カ ka
キ ki
ク ku
ケ ke
コ ko
サ sa
シ shi
ス su
セ se
ソ so
タ ta
チ chi
ツ tsu
テ te
ト to
ナ na
ニ ni
ヌ nu
ネ ne
ノ no
ハ ha
ヒ hi
フ fu
ヘ he
ホ ho
マ ma
ミ mi
ム mu
メ me
モ mo
ヤ ya
ユ yu
ヨ yo
ラ ra
リ ri
ル ru
レ re
ロ ro
ワ wa
ヲ wo | said o, rare in katakana
ン n
"""),
    ("kata_marks", "Katakana: dakuten", """
ガ ga
ギ gi
グ gu
ゲ ge
ゴ go
ザ za
ジ ji | from シ
ズ zu | from ス
ゼ ze
ゾ zo
ダ da
ヂ ji | from チ
ヅ zu | from ツ
デ de
ド do
バ ba
ビ bi
ブ bu
ベ be
ボ bo
パ pa
ピ pi
プ pu
ペ pe
ポ po
"""),
    ("kata_yoon", "Katakana: yōon", """
キャ kya
キュ kyu
キョ kyo
シャ sha
シュ shu
ショ sho
チャ cha
チュ chu
チョ cho
ニャ nya
ニュ nyu
ニョ nyo
ヒャ hya
ヒュ hyu
ヒョ hyo
ミャ mya
ミュ myu
ミョ myo
リャ rya
リュ ryu
リョ ryo
ギャ gya
ギュ gyu
ギョ gyo
ジャ ja
ジュ ju
ジョ jo
ビャ bya
ビュ byu
ビョ byo
ピャ pya
ピュ pyu
ピョ pyo
"""),
    ("kata_ext", "Katakana for loanwords", """
ファ fa
フィ fi
フェ fe
フォ fo
ティ ti
ディ di
トゥ tu
ドゥ du
ウィ wi
ウェ we
ウォ wo
ヴァ va
ヴィ vi
ヴ vu
ヴェ ve
ヴォ vo
シェ she
ジェ je
チェ che
ツァ tsa
"""),
]

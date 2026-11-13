# The BDS movement's own boycott targets, from the BDS National Committee's
# "Guide to BDS Boycott & Pressure Corporate Priority Targeting" (published
# 6 December 2024, read 2026-11-14). Each summary restates the reason that
# guide gives; nothing here comes from anywhere else. When the guide changes,
# change this list to match it and update CHECKED.
#
# tier: "consumer" (the BDS movement's consumer boycott priority targets),
# "organic" (grassroots boycotts it did not start but supports) or
# "pressure" (pressure campaigns, boycotting where alternatives exist).

GUIDE = "https://bdsmovement.net/Guide-to-BDS-Boycott"
CHECKED = "2026-11-14"

ORGANIC_REASON = (
    "A grassroots boycott the BDS movement did not start but supports: the guide says these "
    "companies, or their branches or franchisees in Israel, openly supported Israel or gave "
    "in-kind donations to the Israeli military during the war on Gaza."
)

TARGETS = [
    {"id": "chevron", "name": "Chevron", "aliases": ["Caltex", "Texaco"], "tier": "consumer",
     "reason": "The main company extracting the gas Israel claims in the East Mediterranean. Its "
               "petrol stations trade as Chevron, Caltex and Texaco.",
     "links": [GUIDE, "https://boycottchevron.info"]},
    {"id": "intel", "name": "Intel", "aliases": [], "tier": "consumer",
     "reason": "For decades the largest international investor in Israel. Its Kiryat Gat plant is "
               "built on the land of Iraq al-Manshiya, a Palestinian village that was ethnically "
               "cleansed and razed.",
     "links": [GUIDE]},
    {"id": "dell", "name": "Dell", "aliases": ["Dell Technologies"], "tier": "consumer",
     "reason": "Supplies servers and maintenance to the Israeli military under a $150 million 2023 "
               "contract, and runs research in a cyber park the guide says strengthens settlements "
               "in the Naqab.",
     "links": [GUIDE]},
    {"id": "siemens", "name": "Siemens", "aliases": [], "tier": "consumer",
     "reason": "Main contractor for the Euro-Asia Interconnector, an undersea power cable planned to "
               "connect Israel's illegal settlements to Europe. Siemens-branded appliances are sold "
               "worldwide.",
     "links": [GUIDE]},
    {"id": "hp", "name": "HP", "aliases": ["Hewlett Packard", "Hewlett-Packard", "HP Inc", "Hewlett Packard Enterprise", "HPE"],
     "tier": "consumer",
     "reason": "HP Inc and Hewlett Packard Enterprise provide technology to the Israeli government, "
               "military, prisons and police, including the Population and Immigration Authority's "
               "databases.",
     "links": [GUIDE]},
    {"id": "microsoft", "name": "Microsoft", "aliases": ["Xbox"], "tier": "consumer",
     "reason": "Provides Azure cloud and AI services to the Israeli military. The guide asks for "
               "pressure wherever alternatives exist, including boycotting Xbox and gaming.",
     "links": [GUIDE]},
    {"id": "carrefour", "name": "Carrefour", "aliases": [], "tier": "consumer",
     "reason": "Its Israeli franchise partners, Electra Consumer Products and Yenot Bitan, are active "
               "in illegal settlements, and Carrefour-Israel sent gift packages to Israeli soldiers "
               "during the war on Gaza.",
     "links": [GUIDE]},
    {"id": "axa", "name": "AXA", "aliases": [], "tier": "consumer",
     "reason": "Holds about $150 million in shares and bonds of companies arming Israel, including "
               "Boeing and General Dynamics.",
     "links": [GUIDE]},
    {"id": "reebok", "name": "Reebok", "aliases": [], "tier": "consumer",
     "reason": "Signed a sponsorship contract in 2025 with the Israel Football Association, whose "
               "leagues include teams in illegal settlements.",
     "links": [GUIDE]},
    {"id": "disney-plus", "name": "Disney+", "aliases": ["Disney Plus"], "tier": "consumer",
     "reason": "The guide asks people to cancel or not start Disney+ subscriptions, saying Disney and "
               "Marvel films cast actors who act as cultural ambassadors for Israel.",
     "links": [GUIDE]},
    {"id": "teva", "name": "Teva", "aliases": ["Teva Pharmaceutical Industries", "Teva Pharmaceuticals"], "tier": "consumer",
     "reason": "An Israeli generic drug maker that has supported Israel's war on Gaza since October "
               "2023 and has long profited from the captive Palestinian market.",
     "links": [GUIDE]},
    {"id": "sodastream", "name": "SodaStream", "aliases": [], "tier": "consumer",
     "reason": "An Israeli company the guide says is complicit in displacing Bedouin Palestinian "
               "citizens in the Naqab, with a history of discrimination against Palestinian workers.",
     "links": [GUIDE]},
    {"id": "remax", "name": "RE/MAX", "aliases": ["Remax"], "tier": "consumer",
     "reason": "Markets and sells property in illegal Israeli settlements in the occupied West Bank, "
               "including East Jerusalem.",
     "links": [GUIDE]},
    {"id": "israeli-produce", "name": "Israeli produce", "aliases": ["Product of Israel"], "tier": "consumer",
     "reason": "Fruit, vegetables and wine labelled \"Product of Israel\". The guide says these often "
               "include produce of illegal settlements.",
     "links": [GUIDE]},
    {"id": "mcdonalds", "name": "McDonald's", "aliases": [], "tier": "organic", "reason": ORGANIC_REASON, "links": [GUIDE]},
    {"id": "coca-cola", "name": "Coca-Cola", "aliases": [], "tier": "organic", "reason": ORGANIC_REASON, "links": [GUIDE]},
    {"id": "burger-king", "name": "Burger King", "aliases": [], "tier": "organic", "reason": ORGANIC_REASON, "links": [GUIDE]},
    {"id": "papa-johns", "name": "Papa John's", "aliases": [], "tier": "organic", "reason": ORGANIC_REASON, "links": [GUIDE]},
    {"id": "pizza-hut", "name": "Pizza Hut", "aliases": [], "tier": "organic", "reason": ORGANIC_REASON, "links": [GUIDE]},
    {"id": "dominos", "name": "Domino's Pizza", "aliases": ["Domino's"], "tier": "organic", "reason": ORGANIC_REASON, "links": [GUIDE]},
    {"id": "wix", "name": "Wix", "aliases": [], "tier": "organic", "reason": ORGANIC_REASON, "links": [GUIDE]},
    {"id": "google", "name": "Google", "aliases": ["Alphabet"], "tier": "pressure",
     "reason": "Project Nimbus, a $1.22 billion contract with Amazon, gives the Israeli government and "
               "military cloud and AI services. In 2024 Google signed a further contract with the "
               "Israeli military.",
     "links": [GUIDE]},
    {"id": "amazon", "name": "Amazon", "aliases": ["Ring"], "tier": "pressure",
     "reason": "Project Nimbus, a $1.22 billion contract with Google, gives the Israeli government and "
               "military cloud and AI services. The guide suggests buying elsewhere, and boycotting "
               "Amazon's Ring cameras.",
     "links": [GUIDE]},
    {"id": "booking", "name": "Booking.com", "aliases": ["Booking Holdings"], "tier": "pressure",
     "reason": "Offers rentals in illegal Israeli settlements and is listed in the UN database of "
               "businesses involved in them.",
     "links": [GUIDE]},
    {"id": "airbnb", "name": "Airbnb", "aliases": [], "tier": "pressure",
     "reason": "Offers rentals in illegal Israeli settlements and is listed in the UN database of "
               "businesses involved in them.",
     "links": [GUIDE]},
    {"id": "expedia", "name": "Expedia", "aliases": [], "tier": "pressure",
     "reason": "Offers rentals in illegal Israeli settlements and is listed in the UN database of "
               "businesses involved in them.",
     "links": [GUIDE]},
]

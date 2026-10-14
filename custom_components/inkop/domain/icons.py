"""Icons (Material Design Icons) for common groceries, matched on Swedish words."""

DEFAULT_ICON = "mdi:cart-outline"

# First match wins, so more specific words come before general ones.
_ICON_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("mdi:egg", ("ägg",)),
    ("mdi:cow", ("mjölk", "grädde", "fil", "yoghurt", "yogurt", "kvarg", "smör")),
    ("mdi:cheese", ("ost",)),
    ("mdi:food-croissant", ("croissant", "kanelbulle", "bulle")),
    ("mdi:baguette", ("baguette", "frallor", "fralla")),
    ("mdi:bread-slice", ("bröd", "knäcke", "toast")),
    ("mdi:food-apple", ("äpple", "päron", "banan", "frukt", "druv", "persika")),
    ("mdi:fruit-citrus", ("citron", "apelsin", "lime", "clementin")),
    ("mdi:carrot", ("morot", "morötter", "rotfrukt", "palsternack")),
    ("mdi:leaf", ("sallad", "spenat", "gurka", "kål", "broccoli", "gröns")),
    ("mdi:fruit-grapes", ("tomat", "paprika")),
    ("mdi:food-drumstick", ("kyckling", "kalkon")),
    (
        "mdi:food-steak",
        ("köttfärs", "nötfärs", "färs", "biff", "fläsk", "korv", "kött"),
    ),
    ("mdi:fish", ("lax", "fisk", "torsk", "räk", "tonfisk", "sill")),
    ("mdi:pasta", ("pasta", "spaghetti", "makaroner", "nudlar", "lasagne")),
    ("mdi:rice", ("ris", "couscous", "bulgur", "quinoa")),
    ("mdi:coffee", ("kaffe", "te", "kakao")),
    ("mdi:beer", ("öl", "cider")),
    ("mdi:glass-wine", ("vin", "bubbel")),
    ("mdi:bottle-soda", ("läsk", "juice", "vatten", "saft", "mineral")),
    ("mdi:cookie", ("kex", "kaka", "choklad", "godis", "chips")),
    ("mdi:ice-cream", ("glass",)),
    ("mdi:paper-roll", ("toalettpapper", "hushållspapper", "papper")),
    ("mdi:spray-bottle", ("diskmedel", "tvättmedel", "rengöring", "städ")),
    ("mdi:shaker", ("salt", "peppar", "krydda", "socker", "mjöl")),
)


def icon_for(name: str) -> str:
    """Pick an icon for an item name; compound words match on their parts.

    Example: "havremjölk" gets the milk icon. Unknown items get a cart.
    """
    text = name.casefold()
    for icon, words in _ICON_KEYWORDS:
        if any(word in text for word in words):
            return icon
    return DEFAULT_ICON

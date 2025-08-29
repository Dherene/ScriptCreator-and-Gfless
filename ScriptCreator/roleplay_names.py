import random

PREFIXES = [
    "Ael", "Bel", "Cor", "Dar", "El", "Fen", "Gor", "Hal",
    "Kal", "Mor", "Thal", "Vor", "Zel", "Ryn", "Syl", "Dra",
    "Tor", "Val", "Xan", "Lys", "Kyr", "Ori", "Jor", "Ser",
    "Mal", "Ner", "Ery", "Alar", "Vey", "Zor",
    "aen", "belu", "corin", "daras", "elin", "fenra", "goran", "halis",
    "kalem", "morin", "thalor", "voren", "zelen", "rynar", "sylen", "draven",
    "torin", "valen", "xanor", "lysin", "kyral", "orien", "joren", "serin",
    "malor", "neris", "eryn", "alaren", "veyra", "zorin"
]

ROOTS = [
    "adan", "bar", "cor", "dun", "el", "far", "gar", "har", "ion",
    "anor", "bel", "dros", "fal", "grim", "lor", "mir", "tor", "ul",
    "thal", "rin", "vor", "sar", "mor", "kar", "nor", "tir", "zan",
    "ryn", "gol", "fen",
    "Adel", "Borin", "Calar", "Durel", "Emin", "Faron", "Galor", "Helin",
    "Iron", "Jarel", "Korin", "Lunor", "Miran", "Narel", "Orrin", "Phael",
    "Quen", "Ralos", "Selor", "Tarin", "Ulric", "Varon", "Worin", "Xarel",
    "Ymir", "Zeran", "Thoren", "Brynn", "Cyran", "Drael"
]

SUFFIXES = [
    "dor", "ion", "mir", "nar", "ric", "thas", "wen",
    "as", "eth", "ian", "or", "uth", "ys", "en", "ir", "oth",
    "el", "ar", "is", "al", "orim", "us", "ael", "ior",
    "ien", "yr", "os", "ethar", "orn", "iel",
    "Ael", "Ien", "Orn", "Eth", "Ul", "Yth", "On", "Er",
    "As", "Ior", "Uth", "Ius", "Oth", "An", "Um", "Yr",
    "Es", "Aris", "Is", "Olin", "Eus", "Ir", "Aur", "Enn",
    "Orim", "Ath", "Ith", "Eal", "Uel", "Oros"
]

def generate_roleplay_name() -> str:
    """Generate a fantasy-style name up to 12 characters."""
    name = random.choice(PREFIXES) + random.choice(ROOTS) + random.choice(SUFFIXES)
    return name[:12]
import random
import json

def draw_tarot_cards(deck_path="tarot_cards.json", num=3):
    with open(deck_path, "r", encoding="utf-8") as f:
        deck = json.load(f)

    drawn = random.sample(deck, num)
    for card in drawn:
        card["position"] = random.choice(["正位", "逆位"])
    return drawn

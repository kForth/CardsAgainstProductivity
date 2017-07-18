import json
from random import shuffle


class Deck:
    def __init__(self, packs):
        self.packs = packs
        self.__load_cards()

    def __load_cards(self):
        decks = self.packs
        decks.append("base_cards")
        self.black_cards = []
        self.white_cards = []
        for d in decks:
            cards = json.load(open('cards/{}.json'.format(d)))
            self.black_cards += cards["cards"]["blackCards"]
            self.white_cards += cards["cards"]["whiteCards"]

        shuffle(self.black_cards)
        shuffle(self.white_cards)

    def draw_black_card(self):
        return self.black_cards.pop()

    def draw_white_card(self):
        return self.white_cards.pop()

    def draw_white_cards(self, num_cards):
        for _ in range(num_cards):
            yield self.draw_white_card()

import json
from glob import glob
from random import shuffle
from time import time, sleep

from flask import Flask, jsonify, make_response, request

from server.runners import Runner

app = Flask(__name__)


def remove_player(username, room_name):
    if room_name in rooms.keys():
        room = rooms[room_name]
        if username in room['players']:
            del room['players'][room['players'].index(username)]
            return True
    return False


def load_deck(decks):
    decks.append("base_cards")
    black_cards = []
    white_cards = []
    for d in decks:
        cards = json.load(open('cards/{}.json'.format(d)))
        black_cards += cards["cards"]["blackCards"]
        white_cards += cards["cards"]["whiteCards"]

    shuffle(black_cards)
    shuffle(white_cards)
    data = {
        'black_cards': black_cards,
        'white_cards': white_cards
    }
    return data


@app.route('/')
def index():
    return app.send_static_file(filename='views/index.html')


@app.route('/join', methods=['POST'])
def join_room():
    if request.is_json:
        data = request.json
        username = data['username']
        room_name = data['room_name']
        if room_name not in rooms.keys():
            return make_response(jsonify({}), 404)
        if 'players' not in rooms[room_name].keys():
            rooms[room_name]['players'] = []
        if username not in rooms[room_name]['players']:
            rooms[room_name]['players'].append(username)
            rooms[room_name]['hands'][username] = [rooms[room_name]['deck']['white_cards'].pop() for i in range(7)]
    return make_response(jsonify({}))


@app.route('/create', methods=['POST'])
def create_room():
    room_data = request.json
    if room_data['name'] in rooms.keys():
        return make_response(jsonify({'error': 'name'}), 409)
    room_data['game_phase'] = 'setup_next'
    room_data['last_game_phase'] = room_data['game_phase']
    room_data['last_card_czar'] = ''
    room_data['card_czar'] = ''
    room_data['black_card'] = {}
    room_data['hands'] = {}
    room_data['players'] = []
    room_data['players_submitted'] = []
    room_data['selected_cards'] = {}
    room_data['points'] = {}
    room_data['deck'] = load_deck(room_data['packs'])
    rooms[room_data['name']] = room_data
    print(rooms)
    return make_response(jsonify({}), 200)


@app.route('/login', methods=['POST'])
def login():
    username = request.json['username']
    if 3 <= len(username) <= 10:
        if username not in usernames:
            usernames.append(username)
        else:
            return make_response(jsonify({}), 409)
        return make_response(jsonify({}), 200)
    else:
        return make_response(jsonify({}), 400)


@app.route('/get/rooms', methods=['GET'])
def get_rooms():
    temp_rooms = list(rooms.values())
    return make_response(jsonify(temp_rooms))


def update_rooms():
    for room_name in rooms.keys():
        room = rooms[room_name]
        if room['game_phase'] == 'setup_next':
            room['card_czar'] = ""
            for player in room['players']:
                if player not in room['hands'].keys():
                    room['hands'][player] = []
                for i in range(len(room['hands'][player]), 7):
                    room['hands'][player].append(room['deck']['white_cards'].pop())
            if len(room['players_submitted']) == len(room['players']) and len(room['players']) >= 2:
                room['last_card_czar'] = room['card_czar']
                room['card_czar'] = get_next_czar(room)
                room['black_card'] = room['deck']['black_cards'].pop()
                room['black_card']['text'] = room['black_card']['text'].replace('_', '________')
                room['game_phase'] = 'select_card'
                room['selected_cards'] = {}
                room['players_submitted'] = []

        elif room['game_phase'] == 'select_card':
            if len(room['players_submitted']) == len(room['players']) - 1:
                room['game_phase'] = 'select_winner'
                room['white_card_title'] = "Submitted Cards"
                room['white_cards'] = list(room['selected_cards'].values())
                room['players_submitted'] = []
        elif room['game_phase'] == 'select_winner':
            if room['card_czar'] in room['players_submitted'] and len(room['selected_cards'][room['card_czar']]) == room['black_card']['pick']:
                room['game_phase'] = 'setup_next'
                room['players_submitted'] = []
            if len(room['white_cards']) < 1:
                room['game_phase'] = 'setup_next'

        room['last_game_phase'] = room['game_phase']


@app.route('/get/room', methods=['POST'])
def get_room():
    data = request.json
    username = data['username']
    room_name = data['room_name']
    room = rooms[room_name]

    if data['submitted'] and username not in room['players_submitted'] and data['game_phase'] == room['game_phase']:
        room['players_submitted'].append(username)
    elif not data['submitted'] and username in room['players_submitted'] and data['game_phase'] == room['game_phase']:
        room['players_submitted'].remove(username)

    player_room = dict(room)
    player_room['hands'] = {}
    player_room['deck'] = {}
    player_room['num_to_select'] = 0

    if room['game_phase'] == 'setup_next':
        player_room['white_card_title'] = 'Your Hand'
        player_room['white_cards'] = room['hands'][username]
        player_room['card_czar'] = ""
    elif room['game_phase'] == 'select_card':
        if player_room['card_czar'] == username:
            player_room['white_card_title'] = 'Players Submitted'
            player_room['white_cards'] = room['players_submitted']
        else:
            player_room['num_to_select'] = room['black_card']['pick']
            player_room['white_cards'] = room['hands'][username]
            player_room['white_card_title'] = "Make a selection"
            if data['submitted'] and data['game_phase'] == room['game_phase'] and len(data['cards']) == room['black_card']['pick']:
                room['selected_cards'][username] = data['cards']
                for card in data['cards']:
                    room['hands'][username].remove(card)
    elif room['game_phase'] == 'select_winner':
        if player_room['card_czar'] == username:
            player_room['num_to_select'] = 1
            if username in player_room['players_submitted'] and data['game_phase'] == player_room['game_phase'] and len(data['cards']) > 0:
                for player in room['selected_cards'].keys():
                    if all([e in data['cards'][0] for e in room['selected_cards'][player]]) and player != room['card_czar']:
                        winner = player
                        print("{} Wins!".format(player))
                        break
                else:
                    winner = "Nobody?"
                room['selected_cards'][username] = list(data['cards'])[0]
                if winner not in room['points'].keys():
                    room['points'][winner] = 0
                room['points'][winner] += 1
                suffix = "" if room['points'][winner] == 1 else "s"
                room['black_card']['text'] = "{0} Wins and now has {1} point{2}!".format(winner, room['points'][winner], suffix)
                print("Winning cards: {}".format(list(data['cards'])))
        else:
            pass

    player_room['submitted'] = username in player_room['players_submitted']

    return make_response(jsonify(player_room))


def get_next_czar(room):
    if room['last_card_czar'] is None or room['card_czar'] not in room['players']:
        index = -1
    else:
        index = list(room['players']).index(room['last_card_czar'])
    if index < 0 or index == len(room['players'])-1:
        index = -1
    last_card_czar = room['players'][index]
    return last_card_czar


@app.route('/get/packs', methods=['GET'])
def get_packs():
    files = glob('cards/*.json')
    packs = []
    for file in files:
        if file == 'cards/base_cards.json':
            continue
        packs.append({
            'id':   file[6:-5],
            'name': json.load(open(file))['name']
        })
    return make_response(jsonify(packs))


def update_function():
    while True:
        tick = time()
        update_rooms()
        sleep(max(0, 2 - (time() - tick)))

rooms = {}
usernames = []
update_runner = Runner(update_function)
update_runner.run()

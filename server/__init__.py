import json
from glob import glob
from random import shuffle

from flask import Flask, jsonify, make_response, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from server.cards import Deck
from server.runners import Runner

app = Flask(__name__)
socketio = SocketIO(app)


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


@socketio.on('connect', namespace='/game')
def connect():
    emit('info', 'Connected!', namespace='/game')


@socketio.on('join', namespace='/game')
def join(data):
    username = data['username']
    room_name = data['room_name']
    join_room(room_name)
    sid = request.sid
    room = rooms[room_name]
    sid_rooms[sid] = room_name
    room['usernames'][sid] = username
    room['connected_players'].append(username)
    num_cards = 7
    if username in room['hands'].keys():
        num_cards -= len(room['hands'][username])
    else:
        room['hands'][username] = []
    room['hands'][username] += decks[room_name].draw_white_cards(num_cards)
    update_room(room_name)


@socketio.on('submit_button', namespace='/game')
def submit(selected_cards=None):
    sid = request.sid
    room_name = sid_rooms[sid]
    room = rooms[room_name]
    username = room['usernames'][sid]
    if username not in room['players_submitted']:
        room['players_submitted'].append(username)
        if selected_cards is not None:
            room['selected_cards'][username] = selected_cards
            if room['game_phase'] == 'select_card':
                for card in selected_cards:
                    room['hands'][username].remove(card)
    update_room(room_name)


@socketio.on('leave', namespace='/game')
def leave():
    sid = request.sid
    room = rooms[sid_rooms[sid]]
    room_name = room["name"]
    leave_room(room_name)
    username = room['usernames'][sid]
    room['connected_players'].remove(room['usernames'][sid])
    del sid_rooms[sid]
    del room['usernames'][sid]
    del room['hands'][username]
    del room['points'][username]
    update_room(room_name)


@socketio.on('disconnect', namespace='/game')
def disconnect():
    sid = request.sid
    room = rooms[sid_rooms[sid]]
    room_name = room["name"]
    leave_room(room_name)
    room['connected_players'].remove(room['usernames'][sid])
    del room['usernames'][sid]
    del sid_rooms[sid]
    if len(room['usernames'].keys()) < 1:
        del decks[room['name']]
        del rooms[room['name']]
    update_room(room_name)


@app.route('/')
def index():
    return app.send_static_file(filename='views/index.html')


@app.route('/create', methods=['POST'])
def create_room():
    room_data = request.json
    if room_data['name'] in rooms.keys():
        return make_response(jsonify({'error': 'name'}), 409)
    room_data['game_phase'] = 'setup_next'
    room_data['card_czar'] = ''
    room_data['black_card'] = {
        'text': '',
        'owner': '',
        'num_select': 0
    }
    room_data['hands'] = {}
    room_data['usernames'] = {}
    room_data['connected_players'] = []
    room_data['players_submitted'] = []
    room_data['selected_cards'] = {}
    room_data['points'] = {}
    decks[room_data['name']] = Deck(room_data['packs'])
    rooms[room_data['name']] = room_data
    return make_response(jsonify({}), 200)


@app.route('/get/rooms', methods=['GET'])
def get_rooms():
    temp_rooms = list(rooms.values())
    return make_response(jsonify(temp_rooms))


def update_room(room_name):
    room = rooms[room_name]

    if room['game_phase'] == 'setup_next':
        for player in room['usernames'].values():
            if player not in room['hands'].keys():
                room['hands'][player] = []
            room['hands'][player] += decks[room_name].draw_white_cards(7 - len(room['hands'][player]))

        if len(room['players_submitted']) == len(room['usernames'].values()) and len(room['usernames'].values()) >= 2:
            room['card_czar'] = get_next_czar(room)
            room['black_card'] = decks[room_name].draw_black_card()
            room['black_card']['text'] = room['black_card']['text'].replace('_', '________')
            room['game_phase'] = 'select_card'
            room['selected_cards'] = {}
            room['players_submitted'] = []

    elif room['game_phase'] == 'select_card':
        if len(room['players_submitted']) == len(room['usernames'].values()) - 1:
            room['game_phase'] = 'select_winner'
            room['white_card_title'] = "Submitted Cards"
            room['white_cards'] = list(room['selected_cards'].values())
            room['players_submitted'] = []

    elif room['game_phase'] == 'select_winner':
        if room['card_czar'] in room['selected_cards'].keys():
            winning_card = room['selected_cards'][room['card_czar']]
            del room['selected_cards'][room['card_czar']]
            winning_player = {" ".join(v): k for k, v in room['selected_cards'].items()}[" ".join(winning_card)]
            if winning_player not in room['points'].keys():
                room['points'][winning_player] = 0
            room['points'][winning_player] += 1
            room['winning_card'] = winning_card
            room['winning_player'] = winning_player
            room['game_phase'] = 'setup_next'
            room['players_submitted'] = []
        if len(room['white_cards']) < 1:
            room['game_phase'] = 'setup_next'

    send_room(room_name)


def send_room(room_name):
    room = rooms[room_name]
    for sid in room['usernames'].keys():
        username = room['usernames'][sid]
        data = {
            'game_phase': room['game_phase'],
            'card_czar': room['card_czar'],
            'black_card': room['black_card']
        }

        if room['game_phase'] == 'setup_next':
            data['num_to_select'] = 0
            data['card_czar'] = ""
            data['submitted'] = username in room['players_submitted']
            if "winning_card" in room.keys():
                data['white_card_title'] = '{} wins the round!'.format(room['winning_player'])
                data['white_cards'] = [room['winning_card']]
            else:
                data['white_card_title'] = 'Your Hand'
                data['white_cards'] = [[e] for e in room['hands'][username]]

        elif room['game_phase'] == 'select_card':
            if data['card_czar'] == username or username in room['selected_cards'].keys():
                data['num_to_select'] = 0
                data['white_card_title'] = 'Players Submitted'
                data['white_cards'] = list([[e] for e in room['selected_cards'].keys()])
            else:
                data['num_to_select'] = room['black_card']['pick']
                data['white_cards'] = [[e] for e in room['hands'][username]]
                data['white_card_title'] = "Make a Selection"

        elif room['game_phase'] == 'select_winner':
            if data['card_czar'] == username:
                data['white_card_title'] = 'Select a Winner'
            else:
                data['white_card_title'] = 'Submitted Cards'
            data['white_cards'] = list(room['selected_cards'].values())
            data['num_to_select'] = 1 if data['card_czar'] == username else 0
            data['submitted'] = username in room['players_submitted']

        emit('update', data, room=sid)


def get_next_czar(room):
    if room['card_czar'] is None or room['card_czar'] not in room['usernames'].values():
        index = -1
    else:
        index = list(room['usernames'].values()).index(room['card_czar'])
    if index < 0 or index == len(room['usernames'].values()) - 1:
        index = -1
    new_czar = list(room['usernames'].values())[index + 1]
    return new_czar


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


@app.route('/check_username', methods=['POST'])
def check_username():
    username = request.json['username']
    room_name = request.json['room']['name']
    if 3 <= len(username) <= 10:
        if username in rooms[room_name]['connected_players']:
            return make_response(jsonify({}), 409)
        return make_response(jsonify({}), 200)
    else:
        return make_response(jsonify({}), 400)

sid_rooms = {}
rooms = {}
decks = {}

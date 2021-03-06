import json
from glob import glob

from flask import Flask, jsonify, make_response, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from server.cards import Deck
from server.runners import Runner

app = Flask(__name__)
socketio = SocketIO(app)

sid_rooms = {}
rooms = {}
decks = {}


def get_next_czar(room):
    if room['card_czar'] is None or room['card_czar'] not in room['usernames'].values():
        index = -1
    else:
        index = list(room['usernames'].values()).index(room['card_czar'])
    if index < 0 or index == len(room['usernames'].values()) - 1:
        index = -1
    new_czar = list(room['usernames'].values())[index + 1]
    return new_czar


@socketio.on('connect', namespace='/game')
def connect():
    print("New Connection")


@socketio.on('message', namespace='/game')
def message(data):
    sid = request.sid
    room = rooms[sid_rooms[sid]]
    author = room['usernames'][sid]
    target = data['target']
    target_sid = {v: k for k, v in room['usernames'].items()}[target]
    emit('alert', 'From: {0} \n "{1}"'.format(author, data['message']), room=target_sid)


@socketio.on('join', namespace='/game')
def join(data):
    sid = request.sid
    username = data['username']
    room_name = data['room_name']
    sid_rooms[sid] = room_name
    room = rooms[room_name]
    room['usernames'][sid] = username
    room['connected_players'].append(username)
    num_cards = room['hand_size']
    if username not in room['points'].keys():
        room['points'][username] = 0
    if username in room['hands'].keys():
        num_cards -= len(room['hands'][username])
    else:
        room['hands'][username] = []
    room['hands'][username] += decks[room_name].draw_white_cards(num_cards)
    join_room(room_name)
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


@socketio.on('unsubmit_button', namespace='/game')
def unsubmit():
    sid = request.sid
    room_name = sid_rooms[sid]
    room = rooms[room_name]
    username = room['usernames'][sid]
    if username in room['players_submitted']:
        room['players_submitted'].remove(username)
    update_room(room_name)


@socketio.on('leave', namespace='/game')
def leave():
    sid = request.sid
    room = rooms[sid_rooms[sid]]
    room_name = room["name"]
    leave_room(room_name)
    username = room['usernames'][sid]
    room['connected_players'].remove(room['usernames'][sid])
    if username == room['card_czar']:
        room['game_phase'] = 'setup_next'
        emit('alert', "The Card Czar has left the room.", room=room_name)
    del sid_rooms[sid]
    del room['usernames'][sid]
    del room['hands'][username]
    del room['points'][username]
    update_room(room_name)


@socketio.on('disconnect', namespace='/game')
def disconnect():
    sid = request.sid
    room = rooms[sid_rooms[sid]]
    username = room['usernames'][sid]
    room_name = room["name"]
    room['connected_players'].remove(room['usernames'][sid])
    leave_room(room_name)
    if username == room['card_czar']:
        room['game_phase'] = 'setup_next'
        emit('alert', "The Card Czar has left the room.", room=room_name)
    del room['usernames'][sid]
    del sid_rooms[sid]
    if len(room['usernames'].keys()) < 1:
        del decks[room['name']]
        del rooms[room['name']]
    else:
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
        'text':       'Waiting for game to start.',
        'num_select': 0
    }
    room_data['min_players'] = 2
    room_data['max_players'] = 10
    room_data['hand_size'] = 7
    room_data['max_points'] = 10
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
            room['hands'][player] += decks[room_name].draw_white_cards(room['hand_size'] - len(room['hands'][player]))

        if len(room['players_submitted']) == len(room['usernames'].values()) and len(room['usernames'].values()) >= \
                room['min_players']:
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
            room['points'][winning_player] += 1
            room['winning_card'] = winning_card
            room['winning_player'] = winning_player
            if room['points'][winning_player] >= room['max_points']:
                emit('alert', "{} has won the game!".format(winning_player), room=room_name)
                for player in room['points']:
                    room['points'][player] = 0
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
            'game_phase': room       ['game_phase'],
            'card_czar': room        ['card_czar'],
            'black_card': room       ['black_card'],
            'points': room           ['points'],
            'connected_players': room['connected_players']
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
            if 'winning_player' in room.keys():
                data['winning_player'] = room['winning_player']

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


@app.route('/get/packs', methods=['GET'])
def get_packs():
    files = glob('cards/*.json')
    packs = []
    for file in files:
        if file == 'cards/base_cards.json':
            continue
        packs.append({
            'id': file                   [6:-5],
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

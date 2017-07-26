var module = angular.module('app', ['onsen', 'ngCookies', 'btford.socket-io']);

module.controller('AppController', function ($scope, $cookies, $http) {
        $scope.nav = function (page) {
            $scope.navi.pushPage('../../../static/views/pages/' + page);
        };

    })
    .factory('socket', function (socketFactory) {
        var socket = socketFactory({
            ioSocket: io.connect('/game')
        });
        socket.forward('error');
        return socket;
    });

module.controller('NavigationController', function ($scope, $http, $cookies) {
    ons.ready(function () {
        $scope.navi.pushPage('../../../static/views/pages/home.html');
    });

    $scope.selectRoom = function(room){
        ons.notification.prompt('What is your name?').then(function (username) {
            $http.post('/check_username', {'room': room, 'username': username})
                .then(function (resp) {
                        if (resp.status == 200) {
                            $scope.username = username;
                            $cookies.put('username', username);
                            checkPrivacy(room);
                        }
                        else {
                            $scope.selectRoom();
                        }
                    },
                    function (resp) {
                        if (resp.status == 400) {
                            ons.notification.alert("Username not valid. Try again!").then($scope.selectRoom);
                        }
                        else if (resp.status == 409) {
                            ons.notification.alert("Username taken!").then($scope.selectRoom);
                        }
                    });
        });
    };

    function checkPrivacy(room){
        if (room.privacy == 'private') {
            ons.notification.prompt('What is the password?').then(function (password) {
                if (password == room.password) {
                    $scope.actuallyJoin(room);
                }
                else {
                    ons.notification.alert("Incorrect Password!");
                }
            });
        }
        else {
            $scope.actuallyJoin(room);
        }

    }

    $scope.actuallyJoin = function(room){
        $cookies.put('room_name', room.name);
        $scope.navi.popPage()
            .then(function () {
                $scope.navi.replacePage('../../../static/views/pages/game.html');
            });
    }

});

module.controller('CreateRoomController', function ($scope, $http, $cookies) {
    $scope.username = $cookies.get('username');
    $scope.isArray = angular.isArray;

    $scope.selected_packs = [];
    $http.get('/get/packs').then(function (resp) {
        $scope.packs = resp.data;
    });

    $scope.createRoom = function () {
        var data = {
            'username': $scope.username,
            'name': $scope.room_name,
            'password': $scope.room_password,
            'privacy': ($scope.room_password != undefined && $scope.room_password.length > 0 ? 'private' : 'public'),
            'packs': $scope.selected_packs
        };

        $http.post('/create', data)
            .then(
                function (ignored) {
                    $cookies.put('username', $scope.username);
                    $scope.actuallyJoin(data);
                },
                function (resp) {
                    if (resp.status == 409) {
                        ons.notification.alert("Room Name Taken.");
                    }
                });

    };

    $scope.selectPack = function (pack) {
        if ($scope.selected_packs.indexOf(pack.id) > -1) {
            $scope.selected_packs.splice($scope.selected_packs.indexOf(pack.id), 1);
        }
        else {
            $scope.selected_packs.push(pack.id);
        }
    };

    $scope.selectAll = function () {
        if ($scope.selected_packs.length != $scope.packs.length) {
            $scope.selected_packs = [];
            $scope.packs.forEach(function (e) {
                $scope.selected_packs.push(e.id);
            });
        }
        else {
            $scope.selected_packs = [];
        }
    };

    $scope.selectPrivacy = function (event) {
        // console.log(event);
    }
});

module.controller('JoinRoomController', function ($scope, $http, $timeout) {
    function loadRooms(){
        $http.get('/get/rooms').then(function (resp) {
            $scope.rooms = resp.data;
            $timeout(loadRooms, 10000);
        });
    }
    $timeout(loadRooms, 0);
});

module.controller('RoomController', function ($scope, $http, $cookies, $timeout, socket) {
    $scope.username = $cookies.get('username');
    $scope.selected_cards = [];
    var cards_to_submit = [];
    $scope.room = {};
    $scope.room.game_phase = '';
    $scope.sidebar_shown = false;

    socket.forward('info', $scope);
    $scope.$on('socket:info', function (ev, data) {
        console.log(data);
    });

    var last_game_phase;
    socket.forward('update', $scope);
    $scope.$on('socket:update', function (ev, data) {
        console.log("UPDATE!!!");
        $scope.room = data;
        if(last_game_phase != $scope.room.game_phase){
            console.log("New Phase");
            $scope.selected_cards = [];
            cards_to_submit = [];
        }
        last_game_phase = $scope.room.game_phase;
    });

    var data = {
        'username': $cookies.get('username'),
        'room_name': $cookies.get('room_name')
    };
    socket.emit('join', data);

    /*
     * Game Phases
     *
     * 1. select_card - Card Czar is set, Black Card is selected, players select White Card(s), czar sees "Fake" cards as submitted, players see hand.
     * 2. select_winner - Card Czar selects winning card, players and czar see submitted cards
     * 3. setup_next - Card czar un-set, point awarded, players get new card(s), players see hands, wait for ready buttons
     *
     */


    $scope.enableMenu = function(){
        console.log("Enable Menu");
        // document.getElementById('menu').open();
    };

    $scope.submitButton = function () {
        socket.emit('submit_button', cards_to_submit);
    };


    $scope.selectCard = function (card) {
        if($scope.selected_cards.indexOf(card.toString()) > -1) {
            $scope.selected_cards = [];
            cards_to_submit = [];
        }
        else if ($scope.selected_cards.length < $scope.room.num_to_select) {
            $scope.selected_cards.push(card.toString());
            cards_to_submit = cards_to_submit.concat(card)
        }
    };

});
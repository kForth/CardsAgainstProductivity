var module = angular.module('app', ['onsen', 'ngCookies', 'btford.socket-io', 'angular-md5']);

module.controller('AppController', function ($scope) {
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

module.controller('NavigationController', function ($scope, $http, $cookies, md5) {
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
                if (md5.createHash(password) == room.password) {
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

module.controller('CreateRoomController', function ($scope, $http, $cookies, md5) {
    $scope.username = $cookies.get('username');
    $scope.isArray = angular.isArray;

    $scope.selected_packs = [];
    $http.get('/get/packs').then(function (resp) {
        $scope.packs = resp.data;
    });

    $scope.createRoom = function () {
        var data = {
            'name': $scope.room_name,
            'privacy': ($scope.room_password != undefined && $scope.room_password.length > 0 ? 'private' : 'public'),
            'owner': $scope.username,
            'password': $scope.room_password == undefined ? undefined : md5.createHash($scope.room_password),
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
    $scope.room = {};
    $scope.room.game_phase = '';
    $scope.selected_cards = [];
    var last_game_phase = '';
    var cards_to_submit = [];

    socket.forward('info', $scope);
    $scope.$on('socket:info', function (ev, data) {
        // console.log(data);
    });

    socket.forward('alert', $scope);
    $scope.$on('socket:alert', function (ev, data) {
        ons.notification.alert(data);
    });

    socket.forward('update', $scope);
    $scope.$on('socket:update', function (ev, data) {
        $scope.room = data;
        if(last_game_phase != $scope.room.game_phase){
            $scope.selected_cards = [];
            cards_to_submit = [];
        }
        last_game_phase = $scope.room.game_phase;
    });

    $scope.submitButton = function () {
        socket.emit('submit_button', cards_to_submit);
    };

    $scope.unsubmitButton = function () {
        socket.emit('unsubmit_button');
    };

    $scope.leaveRoom = function(){
        ons.notification.confirm("Are you sure you want to leave?")
            .then(function(resp){
                if(resp){
                    console.log("Leaving");
                }
            });
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

    $scope.sendMessage = function(){
        $scope.playerOptionsDialog.hide();
        ons.notification.prompt("What is your message?")
            .then(function(resp){
                if(resp != undefined && resp.length > 0){
                    console.log(resp);
                    var data = {
                        'target': $scope.focussedPlayer,
                        'message': resp
                    };
                    socket.emit('message', data);
                    ons.notification.alert("Message Sent");
                }
                else{
                    ons.notification.alert("Message Not Sent");
                }
            });
    };

    $scope.openPlayerOptions = function(player){
        if(player === $scope.username){
            return;
        }
        $scope.focussedPlayer = player;
        $scope.splitter.left.close();
        $scope.playerOptionsDialog.show();
    };

    var data = {
        'username': $cookies.get('username'),
        'room_name': $cookies.get('room_name')
    };
    socket.emit('join', data);

});
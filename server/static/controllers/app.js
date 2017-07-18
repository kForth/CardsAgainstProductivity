var module = angular.module('app', ['onsen', 'ngCookies']);

module.controller('AppController', function ($scope, $cookies, $http) {

    $scope.getUsername = function () {
        $scope.username = undefined;
        ons.notification.prompt('What is your name?').then(function (username) {
            $http.post('/login', {'username': username, 'old': $scope.username})
                .then(function (resp) {
                        if (resp.status == 200) {
                            $scope.username = username;
                            $cookies.put('username', username);
                        }
                        else {
                            $scope.getUsername();
                        }
                    },
                    function (resp) {
                        if(resp.status == 400){
                            ons.notification.alert("Username not valid. Try again!");
                        }
                        else if(resp.status == 409){
                            ons.notification.alert("Username taken!");
                        }
                        $scope.getUsername();
                    });
        });
    };

    $scope.nav = function (page) {
        $cookies.put('username', $scope.username);
        $scope.navi.pushPage('../../../static/views/pages/' + page);
    };


    $scope.username = $cookies.get('username');
    if ($scope.username === undefined) {
        $scope.getUsername();
    }

});

module.controller('NavigationController', function ($scope, $http, $cookies) {
    ons.ready(function () {
        $scope.navi.pushPage('../../../static/views/pages/home.html');
    });


    $scope.joinRoom = function (room) {
        if (room.privacy == 'private') {
            ons.notification.prompt('What is the password?').then(function (password) {
                if (password == room.password) {
                    joinRoom(room);
                }
                else {
                    ons.notification.alert("Incorrect Password!");
                }
            });
        }
        else {
            joinRoom(room);
        }

    };

    function joinRoom(room) {
        var data = {
            'username': $cookies.get('username'),
            'room_name': room.name
        };
        $http.post('/join', data).then(
            function (ignored) {
                $cookies.put('room_name', room.name);
                $scope.navi.popPage()
                    .then(function () {
                        $scope.navi.replacePage('../../../static/views/pages/game.html');
                    });
            },
            function (resp) {

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
            'name': $scope.room_name,
            'password': $scope.room_password,
            'privacy': ($scope.room_password != undefined && $scope.room_password.length > 0 ? 'private' : 'public'),
            'packs': $scope.selected_packs
        };

        $http.post('/create', data)
            .then(
                function (resp) {
                    $scope.joinRoom(data);
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
        console.log(event);
    }
});

module.controller('JoinRoomController', function ($scope, $http, $cookies) {
    $scope.username = $cookies.get('username');

    $http.get('/get/rooms').then(function (resp) {
        $scope.rooms = resp.data;
    });

});

module.controller('RoomController', function ($scope, $http, $cookies, $timeout) {
    $scope.username = $cookies.get('username');
    $scope.selected_cards = [];
    $scope.room = {};
    $scope.room.submitted = false;
    $scope.room.game_phase = '';
    $scope.sidebar_shown = false;

    /*
     * Game Phases
     *
     * 1. select_card - Card Czar is set, Black Card is selected, players select White Card(s), czar sees "Fake" cards as submitted, players see hand.
     * 2. select_winner - Card Czar selects winning card, players and czar see submitted cards
     * 3. setup_next - Card czar un-set, point awarded, players get new card(s), players see hands, wait for ready buttons
     *
     */

    $scope.submitUser = function () {
        console.log("Submit");
        $scope.room.submitted = true;
    };


    $scope.enableMenu = function(){
        console.log("asdf");
        // document.getElementById('menu').open();
    };

    $scope.selectCard = function (card) {
        if ($scope.selected_cards.indexOf(card) > -1) {
            $scope.selected_cards.splice(card, 1);
        }
        else if ($scope.selected_cards.length < $scope.room.num_to_select) {
            $scope.selected_cards.push(card);
        }
    };

    var last_game_phase;
    function updateGame() {
        console.log($scope.selected_cards);
        var data = {
            'room_name': $cookies.get('room_name'),
            'username': $scope.username,
            'submitted': $scope.room.submitted,
            'game_phase': $scope.room.game_phase,
            'cards': $scope.selected_cards
        };
        $http.post('/get/room', data)
            .then(
                function (resp) {
                    $scope.room = resp.data;
                    var game_phase = $scope.room.game_phase;
                    if(last_game_phase != game_phase){
                        console.log(resp.data);
                        $scope.selected_cards = [];
                        $scope.room.submitted = false;
                    }
                    last_game_phase = game_phase;
                });

        $timeout(updateGame, 2000)
    }

    $timeout(updateGame, 0)

});
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# UNO Telegram bot — by demon (@demon12809)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import unittest

os.environ.setdefault(
    "TOKEN",
    "000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
)

from aiogram.types import Chat, User

from game import Game
from game_manager import GameManager
from player import Player
from errors import AlreadyJoinedError, LobbyClosedError, NoGameInChatError, \
    NotEnoughPlayersError


class Test(unittest.TestCase):

    game = None

    def setUp(self):
        self.gm = GameManager()

        self.chat0 = Chat(id=0, type="group")
        self.chat1 = Chat(id=1, type="group")
        self.chat2 = Chat(id=2, type="group")

        self.user0 = User(id=0, first_name="user0", is_bot=False)
        self.user1 = User(id=1, first_name="user1", is_bot=False)
        self.user2 = User(id=2, first_name="user2", is_bot=False)

    def test_new_game(self):
        g0 = self.gm.new_game(self.chat0)
        g1 = self.gm.new_game(self.chat1)

        self.assertListEqual(self.gm.chatid_games[0], [g0])
        self.assertListEqual(self.gm.chatid_games[1], [g1])

    def test_new_game_blocked_when_chat_has_lobby(self):
        g0 = self.gm.new_game(self.chat0)
        self.assertIsNotNone(g0)
        g1 = self.gm.new_game(self.chat0)
        self.assertIsNone(g1)
        self.assertListEqual(self.gm.chatid_games[0], [g0])

    def test_join_game(self):

        self.assertRaises(NoGameInChatError,
                          self.gm.join_game,
                          *(self.user0, self.chat0))

        g0 = self.gm.new_game(self.chat0)

        self.gm.join_game(self.user0, self.chat0)
        self.assertEqual(len(g0.players), 1)

        self.gm.join_game(self.user1, self.chat0)
        self.assertEqual(len(g0.players), 2)

        g0.open = False
        self.assertRaises(LobbyClosedError,
                          self.gm.join_game,
                          *(self.user2, self.chat0))

        g0.open = True
        self.assertRaises(AlreadyJoinedError,
                          self.gm.join_game,
                          *(self.user1, self.chat0))

    def test_leave_game(self):
        self.gm.new_game(self.chat0)

        self.gm.join_game(self.user0, self.chat0)
        self.gm.join_game(self.user1, self.chat0)

        self.assertRaises(NotEnoughPlayersError,
                          self.gm.leave_game,
                          *(self.user1, self.chat0))

        self.gm.join_game(self.user2, self.chat0)
        self.gm.leave_game(self.user0, self.chat0)

        self.assertRaises(NoGameInChatError,
                          self.gm.leave_game,
                          *(self.user0, self.chat0))

    def test_end_game(self):
        self.gm.new_game(self.chat0)

        self.gm.join_game(self.user0, self.chat0)
        self.gm.join_game(self.user1, self.chat0)

        self.assertEqual(len(self.gm.userid_players[0]), 1)

        self.gm.end_game(self.chat0, self.user0)
        self.assertFalse(0 in self.gm.chatid_games)
        self.assertFalse(0 in self.gm.userid_players)
        self.assertFalse(1 in self.gm.userid_players)

    def test_end_game_clears_player_ring(self):
        self.gm.new_game(self.chat0)
        self.gm.join_game(self.user0, self.chat0)
        self.gm.join_game(self.user1, self.chat0)
        game = self.gm.player_for_user_in_chat(self.user0, self.chat0).game
        self.gm.end_game(self.chat0, self.user0)
        self.assertIsNone(game.current_player)

        self.gm.new_game(self.chat0)
        self.gm.join_game(self.user2, self.chat0)

        self.gm.end_game(self.chat0, self.user2)
        self.assertFalse(0 in self.gm.chatid_games)
        self.assertFalse(2 in self.gm.userid_players)

    def test_player_for_user_prefers_newest_game_in_chat(self):
        """Legacy duplicate Game objects per chat: resolve user via newest game."""
        self.gm.new_game(self.chat0)
        self.gm.join_game(self.user0, self.chat0)
        p0 = self.gm.player_for_user_in_chat(self.user0, self.chat0)
        g1 = Game(self.chat0)
        self.gm.chatid_games[0].append(g1)
        p1 = Player(g1, self.user0)
        self.gm.userid_players[self.user0.id].append(p1)
        resolved = self.gm.player_for_user_in_chat_id(self.user0, 0)
        self.assertIs(resolved, p1)

# -*- coding: utf-8 -*-
"""
Process-wide Game Manager singleton for UNO lobbies and matches.
"""

import logging
import time

from core.game import Game
from core.player import Player
from errors import (
    AlreadyJoinedError,
    DeckEmptyError,
    LobbyClosedError,
    NoGameInChatError,
    NotEnoughPlayersError,
)
from promotions import send_promotion_async


class GameManager(object):
    """Manages all active lobbies and running UNO games across chats."""

    def __init__(self):
        self.chatid_games = dict()
        self.userid_players = dict()
        self.userid_current = dict()
        self.user_last_inline_chat = dict()
        self.remind_dict = dict()
        self.team_rematches = dict()
        self.logger = logging.getLogger(__name__)

    def is_game_registered(self, game):
        return game in self.chatid_games.get(game.chat.id, list())

    def has_active_game(self, chat_id):
        games = self.chatid_games.get(chat_id)
        return bool(games)

    def get_active_game(self, chat_id):
        games = self.chatid_games.get(chat_id)
        if not games:
            return None
        return games[-1]

    def get_game_in_chat(self, chat):
        """Return the active game for a Telegram-like chat object or ID."""
        chat_id = getattr(chat, "id", chat)
        return self.get_active_game(int(chat_id))

    def is_active_game(self, game):
        return self.is_game_registered(game)

    def cleanup_inactive_games(self, chat_id):
        games = self.chatid_games.get(chat_id)
        if not games:
            return

        def is_dead_shell(g):
            if g.current_player is None:
                return False
            if g.players:
                return False
            return True

        kept = []
        for g in games:
            ch = getattr(g, "chat", None)
            if ch is None or ch.id != chat_id:
                self.logger.warning("cleanup_inactive_games: dropping mismatched game_id=%s expected_chat_id=%s", id(g), chat_id)
                continue
            if is_dead_shell(g):
                self.logger.debug("cleanup_inactive_games: removing dead shell game_id=%s chat_id=%s", id(g), chat_id)
                continue
            kept.append(g)

        if len(kept) == len(games):
            return
        if kept:
            self.chatid_games[chat_id] = kept
        else:
            del self.chatid_games[chat_id]

    def prune_stale_player_refs_for_user(self, user_id):
        players = self.userid_players.get(user_id)
        if not players:
            return

        valid = [p for p in players if self.is_game_registered(p.game)]
        if len(valid) == len(players):
            return

        self.logger.debug("Pruned stale player refs for user_id=%s removed=%s kept=%s", user_id, len(players) - len(valid), len(valid))
        if valid:
            self.userid_players[user_id] = valid
        else:
            del self.userid_players[user_id]
        cur = self.userid_current.get(user_id)
        if cur is not None and cur not in valid:
            try:
                del self.userid_current[user_id]
            except KeyError:
                pass

    def resolve_inline_player(self, user_id: int):
        self.prune_stale_player_refs_for_user(user_id)
        players = self.userid_players.get(user_id) or []
        active = [p for p in players if self.is_game_registered(p.game)]
        if not active:
            return None

        on_turn = [p for p in active if p.game.started and p.game.current_player.user.id == user_id]
        if len(on_turn) == 1:
            return on_turn[0]
        if len(on_turn) > 1:
            last_chat = self.user_last_inline_chat.get(user_id)
            if last_chat is not None:
                for p in on_turn:
                    if p.game.chat.id == last_chat:
                        return p
            return max(on_turn, key=lambda p: p.anti_cheat)

        last_chat = self.user_last_inline_chat.get(user_id)
        if last_chat is not None:
            for p in active:
                if p.game.chat.id == last_chat:
                    return p

        cur = self.userid_current.get(user_id)
        if cur is not None and cur in active:
            return cur

        return active[0]

    def note_last_inline_chat(self, user_id: int, chat_id: int) -> None:
        self.user_last_inline_chat[user_id] = int(chat_id)

    def new_game(self, chat):
        chat_id = chat.id
        self.cleanup_inactive_games(chat_id)

        if self.has_active_game(chat_id):
            self.logger.info("new_game rejected: chat_id=%s already has an active game/lobby", chat_id)
            return None

        self.logger.debug("Creating new game in chat %s", chat_id)
        game = Game(chat)

        if chat_id not in self.chatid_games:
            self.chatid_games[chat_id] = list()

        self.chatid_games[chat_id].append(game)
        return game

    def join_game(self, user, chat):
        self.logger.info("Joining game with id " + str(chat.id))
        try:
            game = self.chatid_games[chat.id][-1]
        except (KeyError, IndexError):
            raise NoGameInChatError()

        if not game.open:
            raise LobbyClosedError()

        if user.id not in self.userid_players:
            self.userid_players[user.id] = list()

        players = self.userid_players[user.id]

        for player in players:
            if player in game.players:
                raise AlreadyJoinedError()

        try:
            self.leave_game(user, chat)
        except NoGameInChatError:
            pass
        except NotEnoughPlayersError:
            self.end_game(chat, user, reason="not_enough_players")
            if user.id not in self.userid_players:
                self.userid_players[user.id] = list()
            players = self.userid_players[user.id]

        player = Player(game, user)
        if game.started:
            try:
                player.draw_first_hand()
            except DeckEmptyError:
                try:
                    player.leave()
                except Exception:
                    self.logger.exception("join_game rollback failed after deck exhaustion user_id=%s chat_id=%s", user.id, chat.id)
                raise
            game.add_participant(user.id)

        players.append(player)
        self.userid_current[user.id] = player

        try:
            from services import user_service
            user_service.ensure_user_row(user)
            user_service.sync_telegram_profile(user)
        except Exception:
            self.logger.exception("user profile sync on join failed user_id=%s", user.id)

    def leave_game(self, user, chat):
        chat_id = chat.id
        games = self.chatid_games.get(chat_id)
        if not games:
            self.logger.debug("leave_game: no games for chat_id=%s", chat_id)
            raise NoGameInChatError()

        player = self.player_for_user_in_chat(user, chat)
        players = self.userid_players.get(user.id, list())

        if not player:
            for g in games:
                for p in g.players:
                    if p.user.id == user.id:
                        if p == g.current_player:
                            g.turn()
                        p.leave()
                        return
            raise NoGameInChatError()

        game = player.game

        if len(game.players) < 3:
            raise NotEnoughPlayersError()

        if player is game.current_player:
            game.turn()

        player.leave()
        try:
            players.remove(player)
        except ValueError:
            self.logger.warning("leave_game: player missing from userid_players user_id=%s", user.id)

        if self.userid_current.get(user.id, None) is player:
            if players:
                self.userid_current[user.id] = players[0]
            else:
                self.userid_current.pop(user.id, None)
                self.userid_players.pop(user.id, None)

    def cancel_unstarted_lobby(self, chat) -> bool:
        chat_id = getattr(chat, "id", None)
        if chat_id is None:
            return False
        games = self.chatid_games.get(chat_id)
        if not games:
            return False
        game = games[-1]
        if getattr(game, "started", False):
            return False

        self.logger.info("cancel_unstarted_lobby chat_id=%s match_uuid=%s", chat_id, getattr(game, "match_uuid", ""))
        send_promotion_async(chat, chance=0.15)

        for player_in_game in list(game.players):
            this_users_players = self.userid_players.get(player_in_game.user.id, list())
            try:
                this_users_players.remove(player_in_game)
            except ValueError:
                pass

            if this_users_players:
                try:
                    self.userid_current[player_in_game.user.id] = this_users_players[0]
                except KeyError:
                    pass
            else:
                try:
                    del self.userid_players[player_in_game.user.id]
                except KeyError:
                    pass
                try:
                    del self.userid_current[player_in_game.user.id]
                except KeyError:
                    pass

        slot = self.chatid_games.get(chat_id)
        if not slot:
            self.logger.warning("cancel_unstarted_lobby: chat_id=%s missing slot after cleanup", chat_id)
        else:
            try:
                slot.remove(game)
            except ValueError:
                self.logger.warning("cancel_unstarted_lobby: game not in slot chat_id=%s", chat_id)
            if not slot:
                del self.chatid_games[chat_id]

        return True

    def end_game(self, chat, user, reason="unknown", abandon_user_id=None):
        self.logger.info("Game in chat " + str(chat.id) + " ended")
        send_promotion_async(chat, chance=0.15)

        player = self.player_for_user_in_chat(user, chat)
        if not player:
            raise NoGameInChatError()

        game = player.game
        players_in_game = list(game.players) if game.current_player else []

        if game.current_player:
            for p in players_in_game:
                p._unlink_from_ring()
            game.current_player = None

        snapshot = None
        if game.started:
            snapshot = {
                "match_id": game.match_uuid,
                "chat_id": chat.id,
                "chat_title": getattr(chat, "title", None) or getattr(chat, "full_name", None) or "",
                "game_mode": game.mode,
                "started": game.started,
                "started_at": game.started_at,
                "turn_count": game.turn_count,
                "participant_ids": list(game.participant_ids),
                "finish_order": list(game.finish_order),
                "end_reason": reason,
            }

        for player_in_game in players_in_game:
            this_users_players = self.userid_players.get(player_in_game.user.id, list())
            try:
                this_users_players.remove(player_in_game)
            except ValueError:
                pass

            if this_users_players:
                try:
                    self.userid_current[player_in_game.user.id] = this_users_players[0]
                except KeyError:
                    pass
            else:
                try:
                    del self.userid_players[player_in_game.user.id]
                except KeyError:
                    pass
                try:
                    del self.userid_current[player_in_game.user.id]
                except KeyError:
                    pass

        slot = self.chatid_games.get(chat.id)
        if not slot:
            self.logger.warning("end_game: chat_id=%s not in chatid_games after player cleanup", chat.id)
        else:
            try:
                slot.remove(game)
            except ValueError:
                self.logger.warning("end_game: game not in chatid_games slot chat_id=%s", chat.id)
            if not slot:
                del self.chatid_games[chat.id]

        if snapshot:
            try:
                from services.match_service import finalize_match
                finalize_match(snapshot)
            except Exception:
                self.logger.exception("finalize_match failed for chat %s", chat.id)
        if getattr(game, "rematch_payload", None):
            payload = dict(game.rematch_payload)
            payload["match_id"] = game.match_uuid
            payload["created_at_ts"] = time.time()
            self.team_rematches[chat.id] = payload

    def player_for_user_in_chat_id(self, user, chat_id):
        self.prune_stale_player_refs_for_user(user.id)
        games = self.chatid_games.get(chat_id, list())
        for game in reversed(games):
            for p in game.players:
                if p.user.id == user.id:
                    self.logger.debug("player_for_user_in_chat_id user_id=%s chat_id=%s player_id=%s game_id=%s", user.id, chat_id, id(p), id(game))
                    return p

        for player in self.userid_players.get(user.id, list()):
            if player.game.chat.id != chat_id:
                continue
            if self.is_game_registered(player.game):
                self.logger.debug("player_for_user_in_chat_id fallback list user_id=%s chat_id=%s player_id=%s game_id=%s", user.id, chat_id, id(player), id(player.game))
                return player
        return None

    def player_for_user_in_chat(self, user, chat):
        return self.player_for_user_in_chat_id(user, chat.id)

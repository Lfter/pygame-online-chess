"""PGN helpers."""

from __future__ import annotations

import io

import chess
import chess.pgn


def board_to_pgn(board: chess.Board) -> str:
    game = chess.pgn.Game()
    game.headers["Event"] = "Pygame Online Chess"
    game.headers["Site"] = "Local"
    game.headers["Result"] = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else "*"
    node = game
    replay_board = chess.Board()
    for move in board.move_stack:
        node = node.add_variation(move)
        replay_board.push(move)
    return str(game)


def pgn_to_board(pgn_text: str) -> chess.Board:
    stream = io.StringIO(pgn_text)
    parsed = chess.pgn.read_game(stream)
    if parsed is None:
        raise ValueError("invalid_pgn")

    board = parsed.board()
    for move in parsed.mainline_moves():
        board.push(move)
    return board

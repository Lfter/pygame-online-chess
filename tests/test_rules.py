from __future__ import annotations

import chess

from game.chess_game import ChessGame


def test_castling_move_is_supported() -> None:
    game = ChessGame()
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"]
    for move in moves:
        assert game.apply_move(move).ok

    result = game.apply_move("e1g1")
    assert result.ok
    assert game.board.piece_at(chess.G1).piece_type == chess.KING
    assert game.board.piece_at(chess.F1).piece_type == chess.ROOK


def test_en_passant_is_supported() -> None:
    game = ChessGame()
    moves = ["e2e4", "h7h5", "e4e5", "d7d5"]
    for move in moves:
        assert game.apply_move(move).ok

    result = game.apply_move("e5d6")
    assert result.ok
    assert game.board.piece_at(chess.D6).piece_type == chess.PAWN
    assert game.board.piece_at(chess.D5) is None


def test_promotion_autofixes_to_queen() -> None:
    game = ChessGame()
    game.board = chess.Board("8/P7/8/8/8/8/8/k6K w - - 0 1")

    result = game.apply_move("a7a8")
    assert result.ok
    piece = game.board.piece_at(chess.A8)
    assert piece is not None
    assert piece.piece_type == chess.QUEEN


def test_threefold_repetition_claim_draw() -> None:
    game = ChessGame()
    repeat_cycle = ["g1f3", "g8f6", "f3g1", "f6g8"] * 3
    applied = 0
    for move in repeat_cycle:
        result = game.apply_move(move)
        if not result.ok:
            assert result.reason == "game_over"
            break
        applied += 1

    assert applied >= 4
    result, reason = game.game_result()
    assert result == "1/2-1/2"
    assert reason in {"threefold_repetition", "fivefold_repetition"}


def test_fifty_move_rule_claim_draw() -> None:
    game = ChessGame()
    game.board = chess.Board("8/8/8/8/8/8/3Q4/3Kk3 w - - 99 1")
    result, reason = game.game_result()
    assert result == "1/2-1/2"
    assert reason in {"fifty_moves", "seventy_five_moves"}


def test_pgn_export_and_import_roundtrip() -> None:
    game = ChessGame()
    for move in ["e2e4", "e7e5", "g1f3", "b8c6"]:
        assert game.apply_move(move).ok

    pgn_text = game.export_pgn()
    clone = ChessGame()
    clone.import_pgn(pgn_text)

    assert clone.board.fen() == game.board.fen()

"""Rendering helpers for chess board and side panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import chess
import pygame


BOARD_SIZE = 640
SQUARE_SIZE = BOARD_SIZE // 8
BOARD_ORIGIN = (40, 40)


@dataclass(slots=True)
class UiTheme:
    light_square: tuple[int, int, int]
    dark_square: tuple[int, int, int]
    selected: tuple[int, int, int]
    legal_hint: tuple[int, int, int]
    last_move: tuple[int, int, int]
    text: tuple[int, int, int]
    panel_bg: tuple[int, int, int]


def square_at_pos(pos: tuple[int, int], flipped: bool = False) -> chess.Square | None:
    x, y = pos
    origin_x, origin_y = BOARD_ORIGIN
    if x < origin_x or y < origin_y:
        return None
    rel_x = x - origin_x
    rel_y = y - origin_y
    if rel_x >= BOARD_SIZE or rel_y >= BOARD_SIZE:
        return None

    file_idx = rel_x // SQUARE_SIZE
    rank_idx = 7 - (rel_y // SQUARE_SIZE)

    if flipped:
        file_idx = 7 - file_idx
        rank_idx = 7 - rank_idx

    return chess.square(file_idx, rank_idx)


def _square_rect(square: chess.Square, flipped: bool = False) -> pygame.Rect:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)

    if flipped:
        file_idx = 7 - file_idx
        rank_idx = 7 - rank_idx

    x = BOARD_ORIGIN[0] + file_idx * SQUARE_SIZE
    y = BOARD_ORIGIN[1] + (7 - rank_idx) * SQUARE_SIZE
    return pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE)


def draw_board(
    screen: pygame.Surface,
    board: chess.Board,
    theme: UiTheme,
    piece_symbols: dict[str, str],
    selected_square: chess.Square | None,
    legal_targets: Iterable[chess.Square],
    last_move: chess.Move | None,
    flipped: bool,
    piece_font: pygame.font.Font,
) -> None:
    legal_target_set = set(legal_targets)
    for rank in range(8):
        for file_idx in range(8):
            square = chess.square(file_idx, rank)
            rect = _square_rect(square, flipped)
            is_light = (file_idx + rank) % 2 == 0
            color = theme.light_square if is_light else theme.dark_square
            pygame.draw.rect(screen, color, rect)

            if last_move is not None and square in {last_move.from_square, last_move.to_square}:
                pygame.draw.rect(screen, theme.last_move, rect, width=4)

            if selected_square == square:
                pygame.draw.rect(screen, theme.selected, rect, width=5)
            elif square in legal_target_set:
                pygame.draw.circle(screen, theme.legal_hint, rect.center, 8)

            piece = board.piece_at(square)
            if piece is None:
                continue
            color_key = "white" if piece.color == chess.WHITE else "black"
            piece_key = f"piece.{color_key}.{piece.piece_type}"
            symbol = piece_symbols.get(piece_key, piece.symbol())
            label = piece_font.render(symbol, True, theme.text)
            label_rect = label.get_rect(center=rect.center)
            screen.blit(label, label_rect)


def draw_panel(
    screen: pygame.Surface,
    theme: UiTheme,
    messages: list[str],
    panel_font: pygame.font.Font,
    title: str,
    controls: list[str],
) -> None:
    panel_rect = pygame.Rect(720, 40, 320, 640)
    pygame.draw.rect(screen, theme.panel_bg, panel_rect, border_radius=12)

    title_surface = panel_font.render(title, True, theme.text)
    screen.blit(title_surface, (740, 60))

    y = 110
    for line in messages[-12:]:
        rendered = panel_font.render(line, True, theme.text)
        screen.blit(rendered, (740, y))
        y += 28

    y = 430
    for control in controls:
        rendered = panel_font.render(control, True, theme.text)
        screen.blit(rendered, (740, y))
        y += 28

"""Pygame client app for local, AI, and online chess."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import chess
import pygame

from ai.factory import AIOrchestrator
from ai.stockfish_engine import detect_stockfish_path
from client.board_ui import draw_board, draw_panel, square_at_pos
from client.network_client import NetworkClient
from client.settings import load_settings, save_settings
from client.theme import ThemeManager
from game.chess_game import ChessGame
from shared.protocol import make_message


class ChessClientApp:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.settings_path = project_root / "settings.json"
        self.settings = load_settings(self.settings_path)

        pygame.init()
        if self.settings.get("audio", {}).get("enabled", True):
            try:
                pygame.mixer.init()
            except Exception:
                pass

        width = int(self.settings["window"]["width"])
        height = int(self.settings["window"]["height"])
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Pygame Online Chess")
        self.clock = pygame.time.Clock()

        theme_name = self.settings.get("theme", {}).get("name", "default")
        audio_enabled = bool(self.settings.get("audio", {}).get("enabled", True))
        self.theme_manager = ThemeManager(project_root, theme_name=theme_name, audio_enabled=audio_enabled)

        self.running = True
        self.mode = "menu"
        self.messages: list[str] = []

        self.font, self.small_font, self.piece_font = self.theme_manager.load_fonts(
            ui_size=24,
            panel_size=20,
            piece_size=52,
        )
        self.use_unicode_pieces = self.theme_manager.unicode_piece_supported()
        if not self.use_unicode_pieces:
            self.log("提示：当前环境缺少棋子符号字形，已自动回退为字母棋子。")

        self._autodetect_stockfish_path()

        self.game = ChessGame()
        self.selected_square: chess.Square | None = None
        self.legal_targets: set[chess.Square] = set()
        self.last_move: chess.Move | None = None

        self.ai_orchestrator: AIOrchestrator | None = None
        self.ai_mode = "simple"

        self.net = NetworkClient()
        self.online_state: dict[str, Any] = {
            "player_id": "",
            "room_id": "",
            "my_color": "white",
            "game_state": None,
            "pending_undo_from": None,
            "pending_draw_from": None,
            "connection_error": "",
        }
        self.online_fields: dict[str, str] = {
            "name": "玩家",
            "host": str(self.settings.get("network", {}).get("default_host", "127.0.0.1")),
            "port": str(self.settings.get("network", {}).get("default_port", 8765)),
            "room_id": str(self.settings.get("network", {}).get("room_id", "")),
        }
        self.online_field_order = ["name", "host", "port", "room_id"]
        self.online_field_active_idx = 0

        self.preset_index = 0
        self.controls_common = [
            "左键选中与落子",
            "U: 悔棋   D: 求和   R: 认输",
            "P: 导出PGN   I: 从 imports/load.pgn 导入",
            "T: 切换时间控制预设",
            "ESC: 返回主菜单",
        ]

    def _autodetect_stockfish_path(self) -> None:
        ai_settings = self.settings.setdefault("ai", {})
        configured = str(ai_settings.get("stockfish_path", ""))
        detected = detect_stockfish_path(configured, project_root=self.project_root)
        if configured.strip():
            configured_path = str(Path(configured).expanduser())
            if detected:
                if detected != configured_path:
                    ai_settings["stockfish_path"] = detected
                    self.log(f"提示：已回退到可用 Stockfish: {detected}")
                return
            else:
                self.log("警告：已配置的 Stockfish 路径不可用，且未找到内置/系统引擎。")
            return
        if detected:
            ai_settings["stockfish_path"] = detected
            stockfish_bin_marker = "assets/engines/stockfish/bin/"
            normalized_path = detected.replace("\\", "/")
            if stockfish_bin_marker in normalized_path:
                self.log(f"已加载项目内置 Stockfish: {detected}")
            else:
                self.log(f"已自动探测到 Stockfish: {detected}")

    def log(self, text: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.messages.append(f"[{now}] {text}")

    def reset_game(self) -> None:
        self.game = ChessGame()
        tc = self._current_time_control()
        self.game.set_time_control(tc[0], tc[1])
        self.selected_square = None
        self.legal_targets.clear()
        self.last_move = None

    def _current_time_control(self) -> tuple[int, int]:
        presets = self.settings.get("time_control", {}).get("presets", [[300, 3]])
        if not presets:
            return (300, 3)
        base, inc = presets[self.preset_index % len(presets)]
        return (int(base), int(inc))

    def _cycle_time_control(self) -> None:
        presets = self.settings.get("time_control", {}).get("presets", [[300, 3]])
        if not presets:
            return
        self.preset_index = (self.preset_index + 1) % len(presets)
        base, inc = self._current_time_control()
        self.log(f"时间预设切换为 {base // 60}+{inc}")

    def run(self) -> None:
        self.log("欢迎使用 Pygame Online Chess")
        while self.running:
            self._poll_online_messages()
            for event in pygame.event.get():
                self._handle_event(event)
            self._draw()
            self.clock.tick(int(self.settings["window"].get("fps", 60)))

        self._shutdown()

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.mode == "menu":
                    self.running = False
                else:
                    self.mode = "menu"
                return

            if self.mode in {"local", "ai", "online"}:
                self._handle_game_hotkeys(event)
            elif self.mode == "online_setup":
                self._handle_online_setup_keys(event)
            elif self.mode == "menu":
                self._handle_menu_keys(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode == "menu":
                self._handle_menu_click(event.pos)
            elif self.mode == "online_setup":
                self._handle_online_setup_click(event.pos)
            elif self.mode in {"local", "ai"}:
                self._handle_local_board_click(event.pos)
            elif self.mode == "online":
                self._handle_online_board_click(event.pos)

    def _handle_menu_keys(self, event: pygame.event.Event) -> None:
        key_map = {
            pygame.K_1: "local",
            pygame.K_2: "ai_simple",
            pygame.K_3: "ai_stockfish",
            pygame.K_4: "ai_auto",
            pygame.K_5: "online_setup",
            pygame.K_q: "quit",
        }
        action = key_map.get(event.key)
        if action:
            self._trigger_menu_action(action)

    def _handle_menu_click(self, pos: tuple[int, int]) -> None:
        x, y = pos
        buttons = self._menu_buttons()
        for label, action, rect in buttons:
            if rect.collidepoint(x, y):
                self._trigger_menu_action(action)
                break

    def _trigger_menu_action(self, action: str) -> None:
        if action == "local":
            self.mode = "local"
            self.reset_game()
            self.ai_orchestrator = None
            self.log("进入本地双人模式")
            return

        if action in {"ai_simple", "ai_stockfish", "ai_auto"}:
            mode = action.split("_", 1)[1]
            self.mode = "ai"
            self.reset_game()
            self.ai_mode = mode
            self.ai_orchestrator = AIOrchestrator(
                mode=mode,
                simple_depth=int(self.settings["ai"].get("simple_depth", 2)),
                stockfish_path=str(self.settings["ai"].get("stockfish_path", "")),
                stockfish_movetime_ms=int(self.settings["ai"].get("stockfish_movetime_ms", 350)),
                manual_fallback=bool(self.settings["ai"].get("manual_fallback", True)),
            )
            self.log(f"进入人机模式: {mode}")
            return

        if action == "online_setup":
            self.mode = "online_setup"
            self.log("进入联机设置：支持键盘和鼠标点击操作")
            return

        if action == "quit":
            self.running = False

    def _menu_buttons(self) -> list[tuple[str, str, pygame.Rect]]:
        labels = [
            ("1. 本地双人", "local"),
            ("2. 人机（简易AI）", "ai_simple"),
            ("3. 人机（Stockfish）", "ai_stockfish"),
            ("4. 人机（自动回退）", "ai_auto"),
            ("5. 联机模式", "online_setup"),
            ("Q. 退出", "quit"),
        ]
        out: list[tuple[str, str, pygame.Rect]] = []
        y = 140
        for label, action in labels:
            rect = pygame.Rect(300, y, 460, 58)
            out.append((label, action, rect))
            y += 72
        return out

    def _handle_game_hotkeys(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_u:
            self._undo_action()
        elif event.key == pygame.K_d:
            self._draw_action()
        elif event.key == pygame.K_r:
            self._resign_action()
        elif event.key == pygame.K_p:
            self._export_pgn()
        elif event.key == pygame.K_i:
            self._import_pgn_from_file()
        elif event.key == pygame.K_t:
            self._cycle_time_control()
            if self.mode in {"local", "ai"}:
                self.reset_game()
        elif self.mode == "online" and self.online_state.get("pending_undo_from") and event.key in {
            pygame.K_y,
            pygame.K_n,
        }:
            accepted = event.key == pygame.K_y
            self.net.send(make_message("undo_response", accepted=accepted))
            self.online_state["pending_undo_from"] = None
        elif self.mode == "online" and self.online_state.get("pending_draw_from") and event.key in {
            pygame.K_y,
            pygame.K_n,
        }:
            accepted = event.key == pygame.K_y
            self.net.send(make_message("draw_response", accepted=accepted))
            self.online_state["pending_draw_from"] = None

    def _undo_action(self) -> None:
        if self.mode == "online":
            if self.net.connected:
                self.net.send(make_message("undo_request"))
                self.log("已发送悔棋请求")
            return

        if self.mode == "ai":
            undone = self.game.undo_last(2)
        else:
            undone = self.game.undo_last(1)

        if undone:
            self.log("本地悔棋成功")
        else:
            self.log("当前无法悔棋")

    def _draw_action(self) -> None:
        if self.mode == "online":
            if self.net.connected:
                self.net.send(make_message("offer_draw"))
                self.log("已发送求和请求")
            return

        self.game.force_result("1/2-1/2", "agreed_draw")
        self.log("本地模式：已判和")

    def _resign_action(self) -> None:
        if self.mode == "online":
            if self.net.connected:
                self.net.send(make_message("resign"))
                self.log("已发送认输")
            return

        winner = "0-1" if self.game.turn == "white" else "1-0"
        self.game.force_result(winner, "resignation")
        self.log("本地认输")

    def _export_pgn(self) -> None:
        exports_dir = self.project_root / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        pgn = self._current_pgn()
        if not pgn.strip():
            self.log("没有可导出的 PGN")
            return

        path = exports_dir / f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
        path.write_text(pgn, encoding="utf-8")
        self.log(f"PGN 已导出: {path.name}")

    def _import_pgn_from_file(self) -> None:
        path = self.project_root / "imports" / "load.pgn"
        if not path.exists():
            self.log("未找到 imports/load.pgn")
            return

        try:
            self.game.import_pgn(path.read_text(encoding="utf-8"))
            self.last_move = self.game.board.move_stack[-1] if self.game.board.move_stack else None
            self.log("已导入 PGN")
            if self.mode == "online":
                self.log("联机模式不允许本地导入，当前仅用于本地/人机")
        except Exception as exc:
            self.log(f"导入 PGN 失败: {exc}")

    def _current_pgn(self) -> str:
        if self.mode == "online":
            game_state = self.online_state.get("game_state")
            if isinstance(game_state, dict):
                return str(game_state.get("pgn", ""))
        return self.game.export_pgn()

    def _handle_local_board_click(self, pos: tuple[int, int]) -> None:
        if self.game.is_game_over():
            return

        square = square_at_pos(pos, flipped=False)
        if square is None:
            return

        board = self.game.board
        if self.selected_square is None:
            piece = board.piece_at(square)
            if piece is None:
                return
            if self.mode == "ai" and piece.color != chess.WHITE:
                return
            if piece.color != board.turn:
                return

            self.selected_square = square
            self.legal_targets = {
                move.to_square for move in board.legal_moves if move.from_square == square
            }
            return

        from_sq = self.selected_square
        self.selected_square = None
        self.legal_targets.clear()

        if from_sq == square:
            return

        self._play_local_move(from_sq, square)

    def _play_local_move(self, from_sq: chess.Square, to_sq: chess.Square) -> None:
        move_uci = chess.square_name(from_sq) + chess.square_name(to_sq)
        move = chess.Move.from_uci(move_uci)
        is_capture = move in self.game.board.legal_moves and self.game.board.is_capture(move)

        result = self.game.apply_move(move_uci)
        if not result.ok:
            self.log(f"非法走子: {result.reason}")
            return

        self.last_move = chess.Move.from_uci(result.move_uci or move_uci)
        self._play_move_sound(is_capture)

        if self.mode == "ai" and not self.game.is_game_over() and self.game.turn == "black":
            self._play_ai_move()

    def _play_ai_move(self) -> None:
        if self.ai_orchestrator is None:
            return

        try:
            move = self.ai_orchestrator.choose_move(self.game.board)
        except FileNotFoundError:
            self.log("Stockfish 未找到（内置与系统均不可用）。请检查 settings.json 的 ai.stockfish_path")
            return
        except Exception as exc:
            self.log(f"AI 计算失败: {exc}")
            return

        is_capture = self.game.board.is_capture(move)
        result = self.game.apply_move(move.uci())
        if result.ok:
            self.last_move = chess.Move.from_uci(result.move_uci or move.uci())
            self._play_move_sound(is_capture)
            self.log(f"AI 落子: {move.uci()}")

    def _play_move_sound(self, is_capture: bool) -> None:
        sfx_volume = float(self.settings.get("audio", {}).get("sfx_volume", 0.75))
        key = "sfx.capture" if is_capture else "sfx.move"
        self.theme_manager.play_sfx(key, volume=sfx_volume)

    def _handle_online_setup_keys(self, event: pygame.event.Event) -> None:
        active_key = self.online_field_order[self.online_field_active_idx]

        if event.key == pygame.K_TAB:
            self.online_field_active_idx = (self.online_field_active_idx + 1) % len(self.online_field_order)
            return

        if event.key == pygame.K_BACKSPACE:
            self.online_fields[active_key] = self.online_fields[active_key][:-1]
            return

        if event.key == pygame.K_c:
            self._online_connect()
            return
        if event.key == pygame.K_h:
            self._online_create_room()
            return
        if event.key == pygame.K_j:
            self._online_join_room()
            return
        if event.key == pygame.K_k:
            self._online_start_game()
            return
        if event.key == pygame.K_o:
            self.mode = "online"
            return

        if event.unicode and event.unicode.isprintable() and len(event.unicode) == 1:
            if active_key == "port" and not event.unicode.isdigit():
                return
            self.online_fields[active_key] += event.unicode

    def _online_setup_field_rects(self) -> list[tuple[str, pygame.Rect]]:
        rects: list[tuple[str, pygame.Rect]] = []
        y = 130
        for key in self.online_field_order:
            rects.append((key, pygame.Rect(80, y, 560, 42)))
            y += 58
        return rects

    def _online_setup_buttons(self) -> list[tuple[str, str, pygame.Rect]]:
        return [
            ("连接服务器", "connect", pygame.Rect(80, 385, 165, 44)),
            ("创建房间", "create_room", pygame.Rect(255, 385, 165, 44)),
            ("加入房间", "join_room", pygame.Rect(430, 385, 165, 44)),
            ("开始对局", "start_game", pygame.Rect(80, 439, 165, 44)),
            ("进入棋盘", "open_board", pygame.Rect(255, 439, 165, 44)),
        ]

    def _handle_online_setup_click(self, pos: tuple[int, int]) -> None:
        for idx, (_, rect) in enumerate(self._online_setup_field_rects()):
            if rect.collidepoint(pos):
                self.online_field_active_idx = idx
                return

        for _, action, rect in self._online_setup_buttons():
            if rect.collidepoint(pos):
                self._run_online_setup_action(action)
                return

    def _run_online_setup_action(self, action: str) -> None:
        if action == "connect":
            self._online_connect()
            return
        if action == "create_room":
            self._online_create_room()
            return
        if action == "join_room":
            self._online_join_room()
            return
        if action == "start_game":
            self._online_start_game()
            return
        if action == "open_board":
            self.mode = "online"
            self.log("已切换到联机棋盘界面")

    def _online_connect(self) -> None:
        host = self.online_fields["host"].strip() or "127.0.0.1"
        port_raw = self.online_fields["port"].strip() or "8765"
        try:
            port = int(port_raw)
        except ValueError:
            self.log("端口格式无效")
            return

        try:
            self.net.connect(host, port)
            self.online_state["connection_error"] = ""
            self.net.send(
                make_message(
                    "hello",
                    name=self.online_fields["name"].strip() or "玩家",
                    player_id=self.online_state.get("player_id", ""),
                )
            )
            self.log(f"已连接 {host}:{port}")
        except Exception as exc:
            self.online_state["connection_error"] = str(exc)
            self.log(f"连接失败: {exc}")

    def _online_create_room(self) -> None:
        if not self.net.connected:
            self.log("请先连接服务器")
            return
        base, inc = self._current_time_control()
        self.net.send(make_message("create_room", base_seconds=base, increment_seconds=inc))
        self.log("已发送建房请求")

    def _online_join_room(self) -> None:
        if not self.net.connected:
            self.log("请先连接服务器")
            return
        room_id = self.online_fields["room_id"].strip().upper()
        payload = {"room_id": room_id} if room_id else {}
        self.net.send(make_message("join_room", **payload))
        self.log("已发送入房请求")

    def _online_start_game(self) -> None:
        if not self.net.connected:
            self.log("请先连接服务器")
            return
        base, inc = self._current_time_control()
        self.net.send(make_message("start_game", base_seconds=base, increment_seconds=inc))
        self.mode = "online"
        self.log("已请求开始对局")

    def _poll_online_messages(self) -> None:
        if not self.net.connected:
            return

        try:
            messages = self.net.poll()
        except Exception as exc:
            self.log(f"网络接收失败: {exc}")
            self.net.close()
            return

        for msg in messages:
            msg_type = msg.get("type")
            if msg_type == "hello":
                self.online_state["player_id"] = str(msg.get("player_id", ""))
                continue
            if msg_type == "room_state":
                self._handle_room_state(msg)
                continue
            if msg_type in {"start_game", "move_result", "game_over"}:
                state = msg.get("game_state")
                if isinstance(state, dict):
                    self._apply_online_game_state(state)
                if msg_type == "game_over":
                    self.log(f"对局结束: {msg.get('result')} ({msg.get('reason')})")
                continue
            if msg_type == "undo_request":
                self.online_state["pending_undo_from"] = msg.get("requester")
                self.log("收到悔棋请求，按 Y 同意 / N 拒绝")
                continue
            if msg_type == "offer_draw":
                self.online_state["pending_draw_from"] = msg.get("requester")
                self.log("收到求和请求，按 Y 同意 / N 拒绝")
                continue
            if msg_type in {"undo_response", "draw_response"}:
                state = msg.get("game_state")
                if isinstance(state, dict):
                    self._apply_online_game_state(state)
                self.log(f"请求响应: {'同意' if msg.get('accepted') else '拒绝'}")
                continue
            if msg_type == "clock_sync":
                state = self.online_state.get("game_state") or {}
                if isinstance(state, dict):
                    state["clock"] = msg.get("clock")
                    self.online_state["game_state"] = state
                continue
            if msg_type == "error":
                self.log(f"服务器错误: {msg.get('code')} {msg.get('detail', '')}")

    def _handle_room_state(self, message: dict[str, Any]) -> None:
        room_id = str(message.get("room_id", ""))
        self.online_state["room_id"] = room_id
        self.online_fields["room_id"] = room_id

        players = message.get("players", [])
        if isinstance(players, list):
            my_id = self.online_state.get("player_id")
            for player in players:
                if not isinstance(player, dict):
                    continue
                if player.get("player_id") == my_id:
                    self.online_state["my_color"] = player.get("color", "white")

        state = message.get("game_state")
        if isinstance(state, dict):
            self._apply_online_game_state(state)

        self.log(f"房间状态更新: {room_id} ({message.get('status')})")

    def _apply_online_game_state(self, game_state: dict[str, Any]) -> None:
        self.online_state["game_state"] = game_state
        fen = game_state.get("fen")
        if isinstance(fen, str) and fen:
            self.game.board = chess.Board(fen)
        moves = self.game.board.move_stack
        self.last_move = moves[-1] if moves else None

    def _handle_online_board_click(self, pos: tuple[int, int]) -> None:
        state = self.online_state.get("game_state")
        if not isinstance(state, dict):
            return

        my_color = str(self.online_state.get("my_color", "white"))
        my_turn = (self.game.turn == "white" and my_color == "white") or (
            self.game.turn == "black" and my_color == "black"
        )
        if not my_turn:
            return

        square = square_at_pos(pos, flipped=(my_color == "black"))
        if square is None:
            return

        board = self.game.board
        if self.selected_square is None:
            piece = board.piece_at(square)
            if piece is None:
                return
            if (piece.color == chess.WHITE and my_color != "white") or (
                piece.color == chess.BLACK and my_color != "black"
            ):
                return
            self.selected_square = square
            self.legal_targets = {
                move.to_square for move in board.legal_moves if move.from_square == square
            }
            return

        from_sq = self.selected_square
        self.selected_square = None
        self.legal_targets.clear()
        if from_sq == square:
            return

        move_uci = chess.square_name(from_sq) + chess.square_name(square)
        self.net.send(make_message("move", move=move_uci))

    def _draw(self) -> None:
        background = self.theme_manager.background_color()
        self.screen.fill(background)

        if self.mode == "menu":
            self._draw_menu()
        elif self.mode == "online_setup":
            self._draw_online_setup()
        else:
            self._draw_game_screen()

        pygame.display.flip()

    def _draw_menu(self) -> None:
        title = self.font.render("Pygame Online Chess", True, (245, 246, 248))
        self.screen.blit(title, (350, 60))

        for label, action, rect in self._menu_buttons():
            pygame.draw.rect(self.screen, (48, 62, 80), rect, border_radius=8)
            text = self.small_font.render(label, True, (245, 246, 248))
            self.screen.blit(text, (rect.x + 18, rect.y + 16))

        draw_panel(
            self.screen,
            self.theme_manager.ui_theme(),
            self.messages,
            self.small_font,
            "消息",
            ["键盘快捷键与鼠标都可操作"],
        )

    def _draw_online_setup(self) -> None:
        ui_theme = self.theme_manager.ui_theme()
        title = self.font.render("联机设置", True, ui_theme.text)
        self.screen.blit(title, (80, 60))

        for idx, (key, rect) in enumerate(self._online_setup_field_rects()):
            active = idx == self.online_field_active_idx
            label = self.small_font.render(f"{key}: {self.online_fields[key]}", True, ui_theme.text)
            border_color = (250, 181, 33) if active else (140, 150, 165)
            pygame.draw.rect(self.screen, (45, 57, 74), rect, border_radius=6)
            pygame.draw.rect(self.screen, border_color, rect, width=2, border_radius=6)
            self.screen.blit(label, (95, rect.y + 9))

        mouse_pos = pygame.mouse.get_pos()
        for label, action, rect in self._online_setup_buttons():
            hovered = rect.collidepoint(mouse_pos)
            bg = (65, 94, 124) if hovered else (48, 62, 80)
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            caption = self.small_font.render(label, True, ui_theme.text)
            self.screen.blit(caption, (rect.x + 16, rect.y + 10))

        draw_panel(
            self.screen,
            ui_theme,
            self.messages,
            self.small_font,
            "联机控制",
            [
                "TAB: 切换字段",
                "C/H/J/K/O: 键盘快捷操作",
                "鼠标点击按钮同样可用",
                "加入房间：room_id 为空时自动匹配",
                "O: 进入棋盘界面",
                "ESC: 返回主菜单",
            ],
        )

    def _draw_game_screen(self) -> None:
        ui_theme = self.theme_manager.ui_theme()
        my_color = "white"
        if self.mode == "online":
            my_color = str(self.online_state.get("my_color", "white"))

        draw_board(
            self.screen,
            self.game.board,
            ui_theme,
            self.theme_manager.piece_symbols(use_unicode=self.use_unicode_pieces),
            self.selected_square,
            self.legal_targets,
            self.last_move,
            flipped=(self.mode == "online" and my_color == "black"),
            piece_font=self.piece_font,
            use_unicode_pieces=self.use_unicode_pieces,
            piece_style=self.theme_manager.piece_style(),
        )

        title = "本地双人"
        if self.mode == "ai":
            title = f"人机对战 ({self.ai_mode})"
        elif self.mode == "online":
            room_id = self.online_state.get("room_id", "")
            title = f"联机对战 房间: {room_id or '-'}"

        game_state_text = self._build_game_status_lines()
        draw_panel(
            self.screen,
            ui_theme,
            self.messages + game_state_text,
            self.small_font,
            title,
            self.controls_common,
        )

    def _build_game_status_lines(self) -> list[str]:
        lines: list[str] = []
        result, reason = self.game.game_result()
        lines.append(f"轮到: {'白方' if self.game.turn == 'white' else '黑方'}")

        if self.game.clock is not None:
            clock = self.game.clock.snapshot()
            lines.append(
                f"棋钟 白 {clock.white_ms // 1000}s / 黑 {clock.black_ms // 1000}s (+{clock.increment_ms // 1000})"
            )

        if self.mode == "online":
            state = self.online_state.get("game_state")
            if isinstance(state, dict):
                clock = state.get("clock")
                if isinstance(clock, dict):
                    lines.append(
                        "联机时钟 白 {0}s / 黑 {1}s".format(
                            int(clock.get("white_ms", 0)) // 1000,
                            int(clock.get("black_ms", 0)) // 1000,
                        )
                    )

        if result:
            lines.append(f"结果: {result} ({reason})")

        if self.online_state.get("pending_undo_from"):
            lines.append("收到悔棋请求: 按 Y/N")
        if self.online_state.get("pending_draw_from"):
            lines.append("收到求和请求: 按 Y/N")

        return lines

    def _shutdown(self) -> None:
        if self.ai_orchestrator is not None:
            self.ai_orchestrator.close()
        self.net.close()

        self.settings["network"]["default_host"] = self.online_fields["host"]
        self.settings["network"]["default_port"] = int(self.online_fields["port"] or "8765")
        self.settings["network"]["room_id"] = self.online_fields["room_id"]
        save_settings(self.settings_path, self.settings)

        pygame.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pygame online chess client")
    parser.add_argument("--root", default=".", help="Project root path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(args.root).resolve()
    app = ChessClientApp(project_root)
    app.run()


if __name__ == "__main__":
    main()

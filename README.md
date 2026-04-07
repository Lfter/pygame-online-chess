# pygame-online-chess

基于 `Pygame` 的现代国际象棋项目，支持：

- 本地双人对弈
- 本地人机对弈（`Stockfish` / 简易 `minimax` AI）
- 联机对弈（中心中转服务器，支持房间号和 IP+端口接入）

项目使用 `python-chess` 提供完整 FIDE 规则判定（王车易位、吃过路兵、升变、三次重复、50步和棋、将杀等）。

## 目录结构

- `client/` Pygame 客户端、UI、输入、主题、网络客户端
- `server/` asyncio TCP 中转服务器、房间与对局管理
- `game/` 棋局封装、棋钟、PGN 导入导出
- `ai/` Stockfish 引擎接入与简易 AI
- `shared/` 协议、DTO、错误码
- `assets/themes/default/` 默认占位主题与音效
- `tests/` 单元测试与集成测试

## 项目独立运行时

本项目已在仓库内自带运行时目录：`.tools/python312`。

不再依赖其他项目路径。你只需要在本仓库内操作。

## 一键准备虚拟环境

```bash
cd /Users/ltzz/Desktop/Python/pygame-online-chess
./scripts/bootstrap_venv.sh
```

## 启动方式

启动服务器：

```bash
cd /Users/ltzz/Desktop/Python/pygame-online-chess
./scripts/run_server.sh
```

可选自定义监听地址：

```bash
./scripts/run_server.sh --host 0.0.0.0 --port 8765
```

启动客户端：

```bash
cd /Users/ltzz/Desktop/Python/pygame-online-chess
./scripts/run_client.sh
```

## 联机模式说明

- `localhost` 双开：同一台设备启动 1 个服务器 + 2 个客户端
- 局域网联机：服务器运行在局域网某台设备，客户端填服务器内网 IP 与端口
- 公网联机：将服务器部署在公网可访问主机，客户端填公网 IP/域名与端口

在联机设置页：

- `TAB` 切换输入字段
- `C` 连接服务器
- `H` 建房
- `J` 加入房间（若 room_id 为空，则按 IP+端口自动匹配等待房间）
- `K` 开始对局
- `O` 进入棋盘
- 也可直接鼠标点击“连接服务器 / 创建房间 / 加入房间 / 开始对局 / 进入棋盘”按钮

## 本地模式快捷键

- `U` 悔棋（人机模式回退双方各一步）
- `D` 本地判和 / 联机发起求和
- `R` 认输
- `P` 导出 PGN 到 `exports/`
- `I` 从 `imports/load.pgn` 导入
- `T` 切换时间控制预设
- `ESC` 回主菜单

## Stockfish 配置

编辑 `settings.json`：

- `ai.mode`: `simple` / `stockfish` / `auto`
- `ai.stockfish_path`: 本机 Stockfish 可执行文件路径（留空时会自动探测 `PATH` 与常见安装位置）
- `ai.manual_fallback`: `true` 时，Stockfish 缺失将报错提示；`false` 时自动回退简易 AI

## 测试

```bash
cd /Users/ltzz/Desktop/Python/pygame-online-chess
./scripts/run_tests.sh
```

## 素材与外观扩展

- 默认主题位于 `assets/themes/default/theme.json`
- 可新建 `assets/themes/<theme_name>/theme.json` 与同名音效资源进行替换
- 缺失字段自动回退默认主题，保证运行稳定

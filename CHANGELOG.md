# Changelog

## 0.1.1 - 2026-04-07

- 新增内嵌 Stockfish 资源目录 `assets/engines/stockfish/`
- 引入“压缩包内置 + 首次自动解压 + 自动赋执行权限”加载机制
- `Stockfish` 探测逻辑改为优先使用项目内嵌引擎，再回退系统路径
- 新增内嵌引擎相关单元测试与许可证来源记录

## 0.1.0 - 2026-04-07

- 初始化 `pygame-online-chess` 项目
- 新增 Pygame 客户端与 asyncio 中转服务器
- 支持本地双人、本地人机（Stockfish/简易AI）与联机对战
- 支持完整 FIDE 规则、PGN 导入导出、悔棋与和棋流程
- 新增主题系统与占位素材接口
- 增加基础单元与集成测试

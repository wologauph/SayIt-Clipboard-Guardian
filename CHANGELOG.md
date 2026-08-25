# 更新日志 (CHANGELOG)

## [v1.0.0] - 2026-08-25

### ✨ 新增特性
- **毫秒级只读监听**：采用 SQLite WAL 只读无锁模式，毫秒级监听 SayIt 本地语音识别数据库 `sayit.db`。
- **强制穿透锁定**：解决 SayIt 原生在 400ms 后自动还原旧剪贴板导致未上屏语音丢失的痛点。在 0ms 首次写入 + 480ms 二次加固覆盖，确保文字 100% 留存在 Windows 剪贴板中。
- **原生 Windows API**：使用 `ctypes` 调用 Windows 原生 `user32`/`kernel32` 剪贴板接口，零第三方依赖。
- **标准工程化打包**：
  - 独立项目架构抽离至 `SayIt-Clipboard-Guardian`。
  - 支持 `setup.ps1` 一键配置 Windows 开机自启（直接采用 `.bat` 方案规避系统静默拦截）。
  - 配备完整的启动、停止、大盘监控与卸载脚本。

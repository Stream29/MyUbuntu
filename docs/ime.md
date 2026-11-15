# Ubuntu 桌面端输入法配置

桌面端以 Ubuntu + GNOME Wayland（及独立 TTY 上的 Sway）与 Fcitx 5 为基础，覆盖中文（Rime + 雾凇拼音）、日语（Mozc）、英文（`keyboard-us`）、Rime OSS 用户数据同步与语音输入（`fcitx5-vinput`）。

## 输入法组与 Rime 目录

- 输入法组：`keyboard-us`、`rime`（默认）、`mozc`
- Rime 用户目录：`~/.local/share/fcitx5/rime`（包含雾凇拼音配置、用户词库与 `sync/`）
- Sway / Qt6 / SDL3 相关集成：
  - [`../bin/sway-fcitx`](../bin/sway-fcitx)
  - [`../home/.config/environment.d/90-fcitx.conf`](../home/.config/environment.d/90-fcitx.conf)
  - [`../home/.config/sway/common.conf`](../home/.config/sway/common.conf)

## Rime OSS 用户数据同步

- 同步脚本：[`../bin/rime-oss-sync`](../bin/rime-oss-sync)
- 用户服务与定时器：[`../home/.config/systemd/user/rime-oss-sync.service`](../home/.config/systemd/user/rime-oss-sync.service)、[`../home/.config/systemd/user/rime-oss-sync.timer`](../home/.config/systemd/user/rime-oss-sync.timer)
- 流程：
  1. 使用 `ossutil` 从 `oss://rime-data/` 拉取同步目录到本地状态目录。
  2. 将其他设备 `installation_id` 的目录复制到 Rime `sync/`。
  3. 通过 Fcitx D-Bus 接口触发 Rime 用户数据同步并合并。
  4. 将本机 `sync/<installation_id>/` 上传回 `oss://rime-data/<installation_id>/`。
- 凭据位置：`~/.config/rime-oss/ossutil.conf`（保留在本地，不入库）。

## 桌面端语音输入（`fcitx5-vinput`）

- 由 `fcitx5-vinput` 插件与 `vinput-daemon.service` 组成，通过 PipeWire 采集 16 kHz 单声道 PCM 发送至阿里云百炼 `qwen3-asr-flash-realtime`。
- 触发键：键盘 Copilot 键（Fn Lock 下发送 `Shift+Super+XF86Assistant`）。
- 用户服务覆写：[`../home/.config/systemd/user/vinput-daemon.service.d/override.conf`](../home/.config/systemd/user/vinput-daemon.service.d/override.conf)（`VINPUT_CAPTURE_IDLE_DESTROY_MS=60000`）。
- 凭据位置：`~/.config/vinput/config.json`（保留在本地，不入库）。

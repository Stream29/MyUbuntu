# Ubuntu GNOME 桌面设置与扩展清单

记录 Ubuntu GNOME Shell（当前基线 `50.1` / Wayland）的声明式桌面设置、快捷键、扩展清单及系统扩展本地修复。

## 文件组成

- [`../gnome/dconf-settings.ini`](../gnome/dconf-settings.ini)：经脱敏与筛选的 `dconf` 关键配置（`dconf load /` 兼容格式）。
- [`../gnome/extensions.json`](../gnome/extensions.json)：用户扩展（`~/.local/share/gnome-shell/extensions/`）与系统扩展（`/usr/share/gnome-shell/extensions/`）清单。
- [`../gnome/patches/ubuntu-appindicators.patch`](../gnome/patches/ubuntu-appindicators.patch)：`/usr/share/gnome-shell/extensions/ubuntu-appindicators@ubuntu.com/` 的本地 JS 修复补丁。
- [`../gnome/patches/ding.patch`](../gnome/patches/ding.patch)：`/usr/share/gnome-shell/extensions/ding@rastersoft.com/`（v105）的注销关会话保护补丁。
- [`../gnome/patches/clipboard-indicator.patch`](../gnome/patches/clipboard-indicator.patch)：`~/.local/share/gnome-shell/extensions/clipboard-indicator@tudmotu.com/`（v74）的 `disable()` 引用泄漏修复与缓存图片按需懒加载补丁。

## 关键行为与设计说明

### 1. Sway 风格 `Super+F` 合成器级真全屏

- `org.gnome.desktop.wm.keybindings toggle-fullscreen` 绑定为 `['<Super>f']`。
- 与 `Super+Up`（`tiling-assistant` 最大化）或 `Alt+F10` 不同，`toggle-fullscreen` 属于 Mutter 合成器级真全屏，直接覆盖顶部状态栏和左侧 Ubuntu Dock。
- `org.gnome.shell.extensions.dash-to-dock autohide-in-fullscreen` 保持默认 `false`，全屏时 Dock 不仅隐藏，还会移除边缘压力触发屏障。
- `tiling-assistant@ubuntu.com` 在执行半屏/最大化快捷键前会自动调用 `unmake_fullscreen()`，全屏与平铺快捷键可直接衔接。

### 2. 为何不直接整库导入 `~/.config/dconf/user`

- `~/.config/dconf/user` 为二进制数据库，包含 Wi-Fi EAP 配置 UUID、Night Light 坐标、文件选择器历史路径、RDP 证书路径与窗口几何状态等敏感或临时数据，不适合直接入库。
- `org.gnome.desktop.screensaver lock-enabled` 由 [`../bin/caffeine-lock-sync`](../bin/caffeine-lock-sync) 依据 `ubuntu-lock-on-suspend` 和 Caffeine 运行态动态切换，因此不写入静态 `lock-enabled` 值；同理不固化 Caffeine 当前的 `user-enabled` 实时开关态。

### 3. 扩展约束与本地补丁

- Ubuntu 会话模式（`/usr/share/gnome-shell/modes/ubuntu.json`）锁定了 `ding@rastersoft.com`、`ubuntu-appindicators@ubuntu.com`、`ubuntu-dock@ubuntu.com`、`tiling-assistant@ubuntu.com` 等系统扩展；对这些扩展的修改必须作用于 `/usr/share/gnome-shell/extensions/`（`root:root`），用户目录同 UUID 覆写不会生效。
- `ding@rastersoft.com` 已升级为上游 GTK4 `v105`，移除显示重连时的同步 `/proc/*/cmdline` 扫描；并应用 [`../gnome/patches/ding.patch`](../gnome/patches/ding.patch)，在 `global` `'shutdown'`、`SessionOver` 与 `org.gnome.SessionManager` 消失时阻止注销途中以 `1ms` 间隔重新拉起 GTK4 `ding.js` 子进程（避免在 `graphical-session.target` 停止后误唤醒 `xdg-desktop-portal.service` 并阻塞 `gnome-session-restart-dbus.service`）。
- `ubuntu-appindicators@ubuntu.com` 修复了 `Util.Logger.warning` 拼写错误及 `this._proxy?.g_name_owner` 空引用异常；包更新覆盖后可参考 [`../gnome/patches/ubuntu-appindicators.patch`](../gnome/patches/ubuntu-appindicators.patch) 重新核对。
- `clipboard-indicator@tudmotu.com`（用户扩展 `v74`）应用 [`../gnome/patches/clipboard-indicator.patch`](../gnome/patches/clipboard-indicator.patch)：修复 `favoritesSection` / `historySection`（`PopupMenuSection`）包裹于 `St.ScrollView` 时未在 `destroy()` 中调用 `.destroy()` 断开 `Main.sessionMode` 订阅及游离菜单控件/闭包滞留的问题，并将磁盘缓存图片的读取改为粘贴时按需加载（落盘后立即释放内存缓冲），避免每次进出 `unlock-dialog` 模式在 `gnome-shell` 原生 C 堆累积约 `33.5 MiB` 泄漏；若扩展升级覆盖后可按该补丁重放。
- `dconf` 中 `enabled-extensions` 历史残留 `pano@elhan.io`（磁盘未安装），清单中已单列在 `stale_dconf_enabled_extensions`。

## 常用导入与校验命令

- 仅恢复 `Super+F` 全屏键位：
  ```bash
  gsettings set org.gnome.desktop.wm.keybindings toggle-fullscreen "['<Super>f']"
  ```
- 合并导入仓库中的声明式 GNOME 设置（不覆盖未列出的其他键）：
  ```bash
  dconf load / < gnome/dconf-settings.ini
  ```
- 核对当前扩展启用与运行状态：
  ```bash
  gnome-extensions list --details
  ```

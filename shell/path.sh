# Put this repository's command directory first and deduplicate PATH entries.
for _devicemanagement_bin in \
    "$HOME/ACodeSpace/push/DeviceManagement/MyUbuntu/bin" \
    "$HOME/ACodeSpace/push/DeviceManagement/MyAndroid/bin" \
    "$HOME/ACodeSpace/push/DeviceManagement/bin"
do
if [ -d "$_devicemanagement_bin" ]; then
    _devicemanagement_prepend() {
        _dm_target=$1
        _dm_old_ifs=$IFS
        _dm_old_flags=$-
        IFS=:
        set -f
        set -- ${PATH:-}
        IFS=$_dm_old_ifs
        case $_dm_old_flags in *f*) ;; *) set +f ;; esac

        _dm_result=$_dm_target
        for _dm_entry do
            case ":$_dm_result:" in
                *:"$_dm_entry":*) continue ;;
            esac
            _dm_result="${_dm_result}:$_dm_entry"
        done
        PATH=$_dm_result
    }
    _devicemanagement_prepend "$_devicemanagement_bin"
    export PATH
    unset -f _devicemanagement_prepend
    unset _dm_target _dm_old_ifs _dm_old_flags _dm_result _dm_entry
fi
done
unset _devicemanagement_bin

# Keep interactive Bash shells inside tmux aligned with the active desktop VT's
# Wayland/X11 display environment written by bin/sway-fcitx.
if [ -n "${BASH_VERSION:-}" ] && [ -n "${TMUX:-}" ]; then
    case $- in
        *i*)
            _devicemanagement_sync_display() {
                local _dm_rc=$1
                local _dm_env="${SWAY_FCITX_ACTIVE_DISPLAY_ENV_FILE:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/active-display.env}"
                if [ -z "${COMP_LINE:-}" ] && [ -r "$_dm_env" ]; then
                    . "$_dm_env"
                fi
                return "$_dm_rc"
            }
            _devicemanagement_sync_display 0 ""
            case "${PROMPT_COMMAND:-}" in
                *_devicemanagement_sync_display*) ;;
                '') PROMPT_COMMAND='_devicemanagement_sync_display "$?" "$_"' ;;
                *) PROMPT_COMMAND="_devicemanagement_sync_display \"\$?\" \"\$_\"; ${PROMPT_COMMAND}" ;;
            esac
            trap '_devicemanagement_sync_display "$?" "$_"' DEBUG
            ;;
    esac
fi

#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

#define SELF_SO_NAME "gdm-filter-non-gdm-sessions.so"

typedef int (*sd_session_get_str_fn)(const char *session, char **out);

static int is_self_token(const char *tok, size_t len) {
    const size_t name_len = sizeof(SELF_SO_NAME) - 1;
    if (len == name_len && memcmp(tok, SELF_SO_NAME, name_len) == 0) {
        return 1;
    }
    if (len > name_len && tok[len - name_len - 1] == '/' &&
        memcmp(tok + len - name_len, SELF_SO_NAME, name_len) == 0) {
        return 1;
    }
    return 0;
}

__attribute__((constructor))
static void strip_self_from_ld_preload(void) {
    const char *preload = getenv("LD_PRELOAD");
    if (preload == NULL || *preload == '\0') {
        return;
    }

    char *buf = strdup(preload);
    if (buf == NULL) {
        return;
    }

    char *out = buf;
    const char *p = preload;
    while (*p != '\0') {
        while (*p == ' ' || *p == ':') {
            p++;
        }
        if (*p == '\0') {
            break;
        }
        const char *start = p;
        while (*p != '\0' && *p != ' ' && *p != ':') {
            p++;
        }
        size_t len = (size_t)(p - start);
        if (!is_self_token(start, len)) {
            if (out != buf) {
                *out++ = ':';
            }
            memcpy(out, start, len);
            out += len;
        }
    }
    *out = '\0';

    if (out == buf) {
        unsetenv("LD_PRELOAD");
    } else {
        setenv("LD_PRELOAD", buf, 1);
    }
    free(buf);
}

int sd_session_get_type(const char *session, char **type) {
    static sd_session_get_str_fn real_get_type = NULL;
    static sd_session_get_str_fn real_get_service = NULL;

    if (real_get_type == NULL) {
        real_get_type = (sd_session_get_str_fn)dlvsym(
            RTLD_NEXT, "sd_session_get_type", "LIBSYSTEMD_209");
        if (real_get_type == NULL) {
            real_get_type = (sd_session_get_str_fn)dlsym(
                RTLD_NEXT, "sd_session_get_type");
        }
    }
    if (real_get_type == NULL) {
        return -ENOSYS;
    }

    int r = real_get_type(session, type);
    if (r < 0 || session == NULL || type == NULL || *type == NULL) {
        return r;
    }

    if (real_get_service == NULL) {
        real_get_service = (sd_session_get_str_fn)dlvsym(
            RTLD_NEXT, "sd_session_get_service", "LIBSYSTEMD_209");
        if (real_get_service == NULL) {
            real_get_service = (sd_session_get_str_fn)dlsym(
                RTLD_NEXT, "sd_session_get_service");
        }
    }
    if (real_get_service == NULL) {
        return r;
    }

    char *service = NULL;
    int sr = real_get_service(session, &service);
    if (sr >= 0 && service != NULL) {
        if (strncmp(service, "gdm", 3) != 0) {
            char *tty_type = strdup("tty");
            if (tty_type != NULL) {
                free(*type);
                *type = tty_type;
            }
        }
        free(service);
    }

    return r;
}

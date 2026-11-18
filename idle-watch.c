#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>
#include "ext-idle-notify-v1-client-protocol.h"

static struct wl_seat *seat;
static struct ext_idle_notifier_v1 *notifier;
static uint32_t notifier_version;

static void reg_global(void *data, struct wl_registry *reg, uint32_t name,
                       const char *iface, uint32_t version)
{
    (void)data;
    if (strcmp(iface, wl_seat_interface.name) == 0 && !seat) {
        seat = wl_registry_bind(reg, name, &wl_seat_interface, 1);
    } else if (strcmp(iface, ext_idle_notifier_v1_interface.name) == 0) {
        notifier_version = version < 2 ? version : 2;
        notifier = wl_registry_bind(reg, name, &ext_idle_notifier_v1_interface,
                                    notifier_version);
    }
}

static void reg_remove(void *data, struct wl_registry *reg, uint32_t name)
{
    (void)data; (void)reg; (void)name;
}

static const struct wl_registry_listener reg_listener = {
    .global = reg_global,
    .global_remove = reg_remove,
};

static void on_idled(void *data, struct ext_idle_notification_v1 *n)
{
    (void)data; (void)n;
    puts("idle");
    fflush(stdout);
}

static void on_resumed(void *data, struct ext_idle_notification_v1 *n)
{
    (void)data; (void)n;
    puts("active");
    fflush(stdout);
}

static const struct ext_idle_notification_v1_listener idle_listener = {
    .idled = on_idled,
    .resumed = on_resumed,
};

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: %s <idle-seconds>\n", argv[0]);
        return 2;
    }
    double secs = atof(argv[1]);
    if (secs <= 0) {
        fprintf(stderr, "idle-seconds must be > 0\n");
        return 2;
    }
    uint32_t timeout_ms = (uint32_t)(secs * 1000.0);

    struct wl_display *dpy = wl_display_connect(NULL);
    if (!dpy) {
        fprintf(stderr, "idle-watch: cannot connect to the Wayland display\n");
        return 1;
    }
    struct wl_registry *reg = wl_display_get_registry(dpy);
    wl_registry_add_listener(reg, &reg_listener, NULL);
    wl_display_roundtrip(dpy);

    if (!seat || !notifier) {
        fprintf(stderr, "idle-watch: compositor lacks wl_seat or ext_idle_notifier_v1\n");
        return 1;
    }

    struct ext_idle_notification_v1 *n;
    if (notifier_version >= 2) {
        /* Ignores idle inhibitors, so a game or video that blocks the
         * screensaver doesn't hide the fact that you walked away. */
        n = ext_idle_notifier_v1_get_input_idle_notification(notifier, timeout_ms, seat);
    } else {
        fprintf(stderr, "idle-watch: WARNING compositor only supports v1; "
                        "games/videos that inhibit idle will hide breaks\n");
        n = ext_idle_notifier_v1_get_idle_notification(notifier, timeout_ms, seat);
    }
    ext_idle_notification_v1_add_listener(n, &idle_listener, NULL);

    while (wl_display_dispatch(dpy) != -1) {
    }
    fprintf(stderr, "idle-watch: lost connection to the compositor\n");
    return 1;
}

/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef ERDOS_H
#define ERDOS_H
#include <stdbool.h>
#include <stdint.h>
struct server;
struct wlr_keyboard;
void erdos_reload(void);
void erdos_action(struct server *, const char *);
void erdos_key(struct server *, struct wlr_keyboard *, uint32_t, bool);
void erdos_cancel_super(void);
void erdos_swipe_begin(struct server *, unsigned);
void erdos_swipe_update(struct server *, double, double);
bool erdos_swipe_owned(void);
void erdos_swipe_end(void);
bool erdos_menu_touchpad(void);
bool erdos_persistent_cycle(void);
void erdos_cycle_end(void);
bool erdos_dynamic(void);
int erdos_minimum(void);
void erdos_workspace_schedule(struct server *);
void erdos_workspace_sync(struct server *);
void erdos_outputs_schedule(struct server *);
#endif

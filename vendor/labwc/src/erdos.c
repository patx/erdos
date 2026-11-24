/* SPDX-License-Identifier: GPL-2.0-only
 * ErdOS: reuse labwc's switcher/actions and event loop, without a desktop daemon. */
#define _POSIX_C_SOURCE 200809L
#include "erdos.h"
#include <glib.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <linux/input-event-codes.h>
#include <xkbcommon/xkbcommon-keysyms.h>
#include <wlr/types/wlr_session_lock_v1.h>
#include <wlr/types/wlr_keyboard.h>
#include <wlr/types/wlr_seat.h>
#include "action.h"
#include "common/spawn.h"
#include "cycle.h"
#include "labwc.h"
#include "view.h"
#include "session-lock.h"
#include "workspaces.h"

static bool dynamic = true, super_enabled = true, touchpad_menu = true;
static bool persistent, fired;
static unsigned fingers, super_candidate;
static int minimum = 2;
static double distance = 120, ratio = 1.5, dx, dy;
static char bindings[8][32];
static const char *keys[] = {"3_up","3_down","3_left","3_right","4_up","4_down","4_left","4_right"};
static const char *defaults[] = {"overview-show","overview-hide","window-previous","window-next","none","none","workspace-next","workspace-previous"};

static bool boolean(GKeyFile *file, const char *key, bool fallback) {
    if (!g_key_file_has_key(file,"session",key,NULL)) return fallback;
    return g_key_file_get_boolean(file,"session",key,NULL);
}
void erdos_reload(void) {
    GKeyFile *file = g_key_file_new();
    char *path = g_build_filename(g_get_user_config_dir(),"erdos","session.ini",NULL);
    g_key_file_load_from_file(file,path,G_KEY_FILE_NONE,NULL); g_free(path);
    dynamic = boolean(file,"dynamic_workspaces",true);
    super_enabled = boolean(file,"super_overview",true);
    touchpad_menu = boolean(file,"menu_touchpad",true);
    minimum = g_key_file_get_integer(file,"session","workspace_count",NULL);
    minimum = CLAMP(minimum ? minimum : 2,1,32);
    g_key_file_free(file);
    for (int i=0;i<8;i++) g_strlcpy(bindings[i],defaults[i],sizeof(bindings[i]));
    distance=120; ratio=1.5;
    const char *bases[] = {"/etc",g_get_user_config_dir()};
    for (int j=0;j<2;j++) {
        file=g_key_file_new(); path=g_build_filename(bases[j],"erdos","gestures.conf",NULL);
        if (g_key_file_load_from_file(file,path,G_KEY_FILE_NONE,NULL)) {
            if (g_key_file_has_key(file,"swipe","distance",NULL)) distance=g_key_file_get_double(file,"swipe","distance",NULL);
            if (g_key_file_has_key(file,"swipe","direction_ratio",NULL)) ratio=g_key_file_get_double(file,"swipe","direction_ratio",NULL);
            for (int i=0;i<8;i++) {
                char *value=g_key_file_get_string(file,"bindings",keys[i],NULL);
                if(value) { g_strlcpy(bindings[i],value,sizeof(bindings[i])); g_free(value); }
            }
        }
        g_free(path); g_key_file_free(file);
    }
    if (!isfinite(distance) || distance<20 || distance>1000) distance=120;
    if (!isfinite(ratio) || ratio<1 || ratio>3) ratio=1.5;
    super_candidate=0;
}
bool erdos_dynamic(void) { return dynamic; }
int erdos_minimum(void) { return minimum; }
bool erdos_menu_touchpad(void) { return touchpad_menu; }
bool erdos_persistent_cycle(void) { return persistent; }
void erdos_cycle_end(void) { persistent=false; }
void erdos_cancel_super(void) { super_candidate=0; }

static void builtin(struct server *server,const char *name,const char *key,const char *value) {
    struct action *action=action_create(name);
    if(!action) return;
    if(key) action_arg_add_str(action,key,value);
    struct wl_list list; wl_list_init(&list); wl_list_insert(&list,&action->link);
    actions_run(NULL,server,&list,NULL); action_free(action);
}
void erdos_action(struct server *server,const char *name) {
    if(server->session_lock_manager->locked) return;
    if(!strcmp(name,"overview-show")) {
        if(server->input_mode!=LAB_INPUT_STATE_PASSTHROUGH) return;
        cycle_toggle_overview(server);
        persistent=server->input_mode==LAB_INPUT_STATE_CYCLE;
    } else if(!strcmp(name,"overview-hide")) {
        if(server->input_mode==LAB_INPUT_STATE_CYCLE) cycle_finish(server,false);
    } else if(!strcmp(name,"window-next") || !strcmp(name,"window-previous")) {
        if(server->input_mode!=LAB_INPUT_STATE_PASSTHROUGH) return;
        struct cycle_filter filter={CYCLE_WORKSPACE_CURRENT,CYCLE_OUTPUT_ALL,CYCLE_APP_ID_ALL};
        cycle_begin(server,!strcmp(name,"window-next")?LAB_CYCLE_DIR_FORWARD:LAB_CYCLE_DIR_BACKWARD,filter);
        cycle_finish(server,true);
    } else if(!strcmp(name,"workspace-next") || !strcmp(name,"workspace-previous")) {
        if(server->input_mode!=LAB_INPUT_STATE_PASSTHROUGH) return;
        struct workspace *next=workspaces_find(server->workspaces.current,!strcmp(name,"workspace-next")?"right":"left",true);
        if(next) workspaces_switch_to(next,true);
    } else if(!strcmp(name,"menu")) {
        builtin(server,"ShowMenu","menu","root-menu");
    } else if(!strcmp(name,"workspaces-menu")) {
        builtin(server,"ShowMenu","menu","client-list-combined-menu");
    } else if(!strcmp(name,"screenshot-window") && server->active_view) {
        struct wlr_box box=server->active_view->current;
        char cmd[160]; snprintf(cmd,sizeof(cmd),"erdos-screenshot geometry '%d,%d %dx%d'",box.x,box.y,box.width,box.height);
        spawn_async_no_shell(cmd);
    }
}
void erdos_key(struct server *server,struct wlr_keyboard *keyboard,uint32_t key,bool pressed) {
    if(!super_enabled || server->session_lock_manager->locked) { super_candidate=0; return; }
    if(pressed) {
        xkb_keysym_t symbol=keyboard ? xkb_state_key_get_one_sym(keyboard->xkb_state,key+8) : XKB_KEY_NoSymbol;
        if(symbol==XKB_KEY_Super_L || symbol==XKB_KEY_Super_R) {
            super_candidate=keyboard && keyboard->num_keycodes==1 ? key+1 : 0;
        } else super_candidate=0;
    } else if(key+1==super_candidate) {
        super_candidate=0;
        erdos_action(server,server->cycle.overview?"overview-hide":"overview-show");
    }
}
void erdos_swipe_begin(struct server *server,unsigned count) {
    erdos_cancel_super(); fingers=0; dx=dy=0; fired=false;
    if(!server->session_lock_manager->locked && (count==3 || count==4)) fingers=count;
}
bool erdos_swipe_owned(void) { return fingers!=0; }
void erdos_swipe_update(struct server *server,double x,double y) {
    if(!fingers || fired) return;
    dx+=x; dy+=y;
    int direction=-1;
    if(fabs(dy)>=distance && fabs(dy)>=ratio*fabs(dx)) direction=dy<0?0:1;
    else if(fabs(dx)>=distance && fabs(dx)>=ratio*fabs(dy)) direction=dx<0?2:3;
    if(direction<0) return;
    fired=true; erdos_action(server,bindings[(fingers==4?4:0)+direction]);
}
void erdos_swipe_end(void) { fingers=0; }

static struct wl_event_source *outputs_idle;
static void outputs_apply(void *data) {
    (void)data; outputs_idle=NULL; spawn_async_no_shell("erdos-displays --apply");
}
void erdos_outputs_schedule(struct server *server) {
    if(!outputs_idle) outputs_idle=wl_event_loop_add_idle(server->wl_event_loop,outputs_apply,server);
}

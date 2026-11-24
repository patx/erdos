// SPDX-License-Identifier: GPL-2.0-only
#include <glib.h>
#include <wlr/types/wlr_scene.h>
#include "buffer.h"
#include "common/macros.h"
#include "common/mem.h"
#include "config/rcxml.h"
#include "cycle.h"
#include "labwc.h"
#include "output.h"
#include "scaled-buffer/scaled-font-buffer.h"

static void
draw_dock_icon(cairo_t *cr, int index, double x)
{
	cairo_save(cr);
	cairo_translate(cr, x, 23);
	cairo_set_line_width(cr, 1.6);
	cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
	cairo_set_line_join(cr, CAIRO_LINE_JOIN_ROUND);
	cairo_set_source_rgb(cr, .71, .82, 1);
	switch (index) {
	case 0: /* compass */
		cairo_arc(cr, 0, 0, 11, 0, 2 * G_PI);
		cairo_stroke(cr);
		cairo_move_to(cr, 5, -5);
		cairo_line_to(cr, 2, 2);
		cairo_line_to(cr, -5, 5);
		cairo_line_to(cr, -2, -2);
		cairo_close_path(cr);
		break;
	case 1: /* folder */
		cairo_move_to(cr, -11, 8);
		cairo_line_to(cr, -11, -8);
		cairo_line_to(cr, -3, -8);
		cairo_line_to(cr, 0, -5);
		cairo_line_to(cr, 11, -5);
		cairo_line_to(cr, 11, 8);
		cairo_close_path(cr);
		break;
	case 2: /* terminal */
		cairo_rectangle(cr, -11, -9, 22, 18);
		cairo_move_to(cr, -7, -4);
		cairo_line_to(cr, -3, 0);
		cairo_line_to(cr, -7, 4);
		cairo_move_to(cr, 1, 4);
		cairo_line_to(cr, 6, 4);
		break;
	case 3: /* sliders */
		for (int row = 0; row < 3; ++row) {
			double y = -7 + row * 7;
			double center = row == 1 ? 5 : -4;
			cairo_move_to(cr, -10, y);
			cairo_line_to(cr, center - 2.5, y);
			cairo_move_to(cr, center + 2.5, y);
			cairo_line_to(cr, 10, y);
			cairo_new_sub_path(cr);
			cairo_arc(cr, center, y, 2.5, 0, 2 * G_PI);
		}
		break;
	case 4: /* Wi-Fi */
		for (int radius = 5; radius <= 15; radius += 5) {
			cairo_new_sub_path(cr);
			cairo_arc(cr, 0, 7, radius, -3 * G_PI / 4, -G_PI / 4);
		}
		cairo_stroke(cr);
		cairo_arc(cr, 0, 7, 1.5, 0, 2 * G_PI);
		cairo_fill(cr);
		break;
	case 5: /* clock */
		cairo_arc(cr, 0, 0, 11, 0, 2 * G_PI);
		cairo_stroke(cr);
		cairo_move_to(cr, 0, -6);
		cairo_line_to(cr, 0, 0);
		cairo_line_to(cr, 4, 3);
		break;
	}
	cairo_stroke(cr);
	cairo_restore(cr);
}


struct dock_status {
	struct wl_listener destroy;
	struct wl_event_source *timer;
	struct scaled_font_buffer *clock;
	struct scaled_font_buffer *battery;
	struct wlr_scene_buffer *battery_icon;
	int cell_width;
	int clock_index;
	float scale;
	char clock_text[32];
	int capacity;
	bool charging;
};

static char *
read_power_property(const char *supply, const char *property)
{
	g_autofree char *path = g_build_filename("/sys/class/power_supply",
		supply, property, NULL);
	char *value = NULL;
	return g_file_get_contents(path, &value, NULL, NULL) ? g_strstrip(value) : NULL;
}

static int
battery_capacity(bool *charging)
{
	g_autoptr(GDir) supplies = g_dir_open("/sys/class/power_supply", 0, NULL);
	if (!supplies) {
		return -1;
	}
	int total = 0;
	int count = 0;
	const char *name;
	while ((name = g_dir_read_name(supplies))) {
		g_autofree char *type = read_power_property(name, "type");
		if (g_strcmp0(type, "Battery") != 0) {
			continue;
		}
		g_autofree char *scope = read_power_property(name, "scope");
		g_autofree char *present = read_power_property(name, "present");
		if (g_strcmp0(scope, "Device") == 0 || g_strcmp0(present, "0") == 0) {
			continue;
		}
		g_autofree char *value = read_power_property(name, "capacity");
		gint64 capacity;
		if (!value || !g_ascii_string_to_signed(value, 10, 0, 100, &capacity, NULL)) {
			continue;
		}
		total += capacity;
		++count;
		g_autofree char *status = read_power_property(name, "status");
		*charging |= g_strcmp0(status, "Charging") == 0;
	}
	return count ? (total + count / 2) / count : -1;
}

static void
update_battery_icon(struct dock_status *status)
{
	struct lab_data_buffer *buffer = buffer_create_cairo(30, 26, status->scale);
	cairo_t *cr = cairo_create(buffer->surface);
	cairo_set_source_rgb(cr, .71, .82, 1);
	cairo_set_line_width(cr, 1.6);
	cairo_set_line_join(cr, CAIRO_LINE_JOIN_ROUND);
	cairo_rectangle(cr, 3, 6.5, 22, 13);
	cairo_stroke(cr);
	cairo_rectangle(cr, 26, 10, 2, 6);
	cairo_fill(cr);
	if (status->charging) {
		cairo_set_source_rgb(cr, .5, .95, .68);
		cairo_move_to(cr, 15, 7.5);
		cairo_line_to(cr, 10, 14);
		cairo_line_to(cr, 14, 14);
		cairo_line_to(cr, 13, 18.5);
		cairo_line_to(cr, 18, 12);
		cairo_line_to(cr, 14, 12);
		cairo_close_path(cr);
		cairo_fill(cr);
	} else if (status->capacity >= 0) {
		if (status->capacity <= 15) {
			cairo_set_source_rgb(cr, 1, .54, .52);
		}
		cairo_rectangle(cr, 5.5, 9, 17 * status->capacity / 100., 8);
		cairo_fill(cr);
	}
	cairo_destroy(cr);
	cairo_surface_flush(buffer->surface);
	wlr_scene_buffer_set_buffer(status->battery_icon, &buffer->base);
	wlr_scene_buffer_set_dest_size(status->battery_icon, 30, 26);
	wlr_buffer_drop(&buffer->base);
}

static void
position_label(struct scaled_font_buffer *label, const char *text, int index, int width)
{
	scaled_font_buffer_update(label, text, MAX(1, width - 8),
		&rc.font_osd, (float[4]){.95, .96, 1, 1}, (float[4]){0});
	wlr_scene_node_set_position(&label->scene_buffer->node,
		index * width + (width - label->width) / 2, 43);
}

static int
refresh_dock_status(void *data)
{
	struct dock_status *status = data;
	g_autoptr(GDateTime) now = g_date_time_new_now_local();
	g_autofree char *time = now ? g_date_time_format(now, "%l:%M %p") : NULL;
	if (time) {
		g_strstrip(time);
	}
	if (time && !g_str_equal(time, status->clock_text)) {
		g_strlcpy(status->clock_text, time, sizeof(status->clock_text));
		position_label(status->clock, time, status->clock_index, status->cell_width);
	}
	bool charging = false;
	int capacity = battery_capacity(&charging);
	if (capacity != status->capacity || charging != status->charging) {
		status->capacity = capacity;
		status->charging = charging;
		g_autofree char *label = capacity >= 0 ? g_strdup_printf("%d%%", capacity) : NULL;
		position_label(status->battery, label ? label : "No battery",
			status->clock_index + 1, status->cell_width);
		update_battery_icon(status);
	}
	if (status->timer) {
		wl_event_source_timer_update(status->timer, 5000);
	}
	return 0;
}

static void
destroy_dock_status(struct wl_listener *listener, void *data)
{
	struct dock_status *status = wl_container_of(listener, status, destroy);
	if (status->timer) {
		wl_event_source_remove(status->timer);
	}
	wl_list_remove(&listener->link);
	free(status);
}

void
overview_dock_create(struct cycle_osd_output *osd_output, const struct wlr_box *output_box)
{
	struct server *server = osd_output->output->server;
	int count = 0;
	while (overview_launchers[count].command) {
		++count;
	}
	int slots = count + 2;
	int width = MIN(88, MAX(1, (output_box->width - 24) / slots));
	int height = 70;
	int dock_x = (output_box->width - slots * width) / 2;
	int dock_y = output_box->height - height - 22;
	osd_output->dock = (struct wlr_box) {
		.x = output_box->x + dock_x,
		.y = output_box->y + dock_y,
		.width = slots * width,
		.height = height,
	};
	osd_output->dock_button_width = width;
	osd_output->dock_button_count = count;
	struct wlr_scene_tree *dock = wlr_scene_tree_create(osd_output->tree);
	wlr_scene_node_set_position(&dock->node, dock_x, dock_y);
	int dock_width = slots * width;
	struct lab_data_buffer *panel = buffer_create_cairo(
		dock_width, height, osd_output->output->wlr_output->scale);
	cairo_t *cr = cairo_create(panel->surface);
	double r = MIN(18, dock_width / 2.);
	cairo_arc(cr, dock_width - r - 1, r + 1, r, -G_PI / 2, 0);
	cairo_arc(cr, dock_width - r - 1, height - r - 1, r, 0, G_PI / 2);
	cairo_arc(cr, r + 1, height - r - 1, r, G_PI / 2, G_PI);
	cairo_arc(cr, r + 1, r + 1, r, G_PI, 3 * G_PI / 2);
	cairo_close_path(cr);
	cairo_set_source_rgba(cr, .09, .105, .14, .96);
	cairo_fill_preserve(cr);
	cairo_set_source_rgba(cr, .45, .51, .62, .45);
	cairo_set_line_width(cr, 1);
	cairo_stroke(cr);
	cairo_set_source_rgba(cr, .45, .51, .62, .3);
	cairo_move_to(cr, (count - 1) * width, 11);
	cairo_line_to(cr, (count - 1) * width, height - 11);
	cairo_stroke(cr);
	for (int i = 0; i <= count; ++i) {
		draw_dock_icon(cr, i, (i + .5) * width);
	}
	cairo_destroy(cr);
	cairo_surface_flush(panel->surface);
	struct wlr_scene_buffer *panel_node = wlr_scene_buffer_create(dock, &panel->base);
	wlr_scene_buffer_set_dest_size(panel_node, dock_width, height);
	wlr_buffer_drop(&panel->base);
	for (int i = 0; i < count; ++i) {
		struct scaled_font_buffer *label = scaled_font_buffer_create(dock);
		position_label(label, overview_launchers[i].label, i, width);
	}
	struct dock_status *status = znew(*status);
	status->capacity = -2; /* Force the first update, including on desktops. */
	status->cell_width = width;
	status->clock_index = count;
	status->scale = osd_output->output->wlr_output->scale;
	status->clock = scaled_font_buffer_create(dock);
	status->battery = scaled_font_buffer_create(dock);
	status->battery_icon = wlr_scene_buffer_create(dock, NULL);
	wlr_scene_node_set_position(&status->battery_icon->node,
		(count + 1) * width + (width - 30) / 2, 10);
	status->destroy.notify = destroy_dock_status;
	wl_signal_add(&dock->node.events.destroy, &status->destroy);
	status->timer = wl_event_loop_add_timer(
		wl_display_get_event_loop(server->wl_display), refresh_dock_status, status);
	refresh_dock_status(status);
}

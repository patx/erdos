// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <drm_fourcc.h>
#include <time.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/render/allocator.h>
#include <wlr/render/swapchain.h>
#include <wlr/types/wlr_buffer.h>
#include <wlr/types/wlr_output_layout.h>
#include <wlr/types/wlr_scene.h>
#include "buffer.h"
#include "config/rcxml.h"
#include "common/box.h"
#include "common/buf.h"
#include "common/lab-scene-rect.h"
#include "common/list.h"
#include "common/mem.h"
#include "cycle.h"
#include "labwc.h"
#include "node.h"
#include "output.h"
#include "scaled-buffer/scaled-font-buffer.h"
#include "scaled-buffer/scaled-icon-buffer.h"
#include "theme.h"
#include "view.h"

struct cycle_osd_thumbnail_item {
	struct cycle_osd_item base;
	struct scaled_font_buffer *normal_label;
	struct scaled_font_buffer *active_label;
	struct lab_scene_rect *active_bg;
	struct wlr_scene_buffer *preview;
	struct wlr_scene_buffer *glow;
	struct wlr_box preview_bounds;
	uint64_t last_revision;
};

static void
render_node(struct server *server, struct wlr_render_pass *pass,
		struct wlr_scene_node *node, int x, int y, double sx, double sy)
{
	switch (node->type) {
	case WLR_SCENE_NODE_TREE: {
		struct wlr_scene_tree *tree = wlr_scene_tree_from_node(node);
		struct wlr_scene_node *child;
		wl_list_for_each(child, &tree->children, link) {
			render_node(server, pass, child, x + node->x, y + node->y, sx, sy);
		}
		break;
	}
	case WLR_SCENE_NODE_BUFFER: {
		struct wlr_scene_buffer *scene_buffer =
			wlr_scene_buffer_from_node(node);
		if (!scene_buffer->buffer) {
			break;
		}
		struct wlr_texture *texture = NULL;
		struct wlr_client_buffer *client_buffer =
			wlr_client_buffer_get(scene_buffer->buffer);
		if (client_buffer) {
			texture = client_buffer->texture;
		}
		if (!texture) {
			break;
		}
		int left = round(x * sx);
		int top = round(y * sy);
		int width = round((x + scene_buffer->dst_width) * sx) - left;
		int height = round((y + scene_buffer->dst_height) * sy) - top;
		if (width < 1 || height < 1) {
			break;
		}
		wlr_render_pass_add_texture(pass, &(struct wlr_render_texture_options){
			.texture = texture,
			.src_box = scene_buffer->src_box,
			.dst_box = {
				.x = left,
				.y = top,
				.width = width,
				.height = height,
			},
			.transform = scene_buffer->transform,
		});
		break;
	}
	case WLR_SCENE_NODE_RECT:
		/* should be unreached */
		wlr_log(WLR_ERROR, "ignoring rect");
		break;
	}
}

static struct wlr_buffer *
render_thumb(struct output *output, struct view *view, int width, int height)
{
	if (!view->content_tree || !output->wlr_output->swapchain
			|| view->current.width < 1 || view->current.height < 1
			|| width < 1 || height < 1) {
		/*
		 * Defensive. Could possibly occur if view was unmapped
		 * with OSD already displayed.
		 */
		return NULL;
	}
	struct server *server = output->server;
	const struct wlr_drm_format *output_format = &output->wlr_output->swapchain->format;
	struct wlr_drm_format alpha_format = *output_format;
	alpha_format.format = DRM_FORMAT_ARGB8888;
	struct wlr_buffer *buffer = NULL;
	if (server->cycle.overview) {
		buffer = wlr_allocator_create_buffer(server->allocator, width, height, &alpha_format);
	}
	if (!buffer) {
		buffer = wlr_allocator_create_buffer(server->allocator, width, height, output_format);
	}
	if (!buffer) {
		wlr_log(WLR_ERROR, "failed to allocate buffer for thumbnail");
		return NULL;
	}
	struct wlr_render_pass *pass = wlr_renderer_begin_buffer_pass(
		server->renderer, buffer, NULL);
	if (!pass) {
		wlr_buffer_drop(buffer);
		return NULL;
	}
	wlr_render_pass_add_rect(pass, &(struct wlr_render_rect_options) {
		.box = { .width = width, .height = height },
		.color = server->cycle.overview ? (struct wlr_render_color){0}
			: (struct wlr_render_color){.045, .052, .072, 1},
		.blend_mode = WLR_RENDER_BLEND_MODE_NONE,
	});
	render_node(server, pass, &view->content_tree->node, 0, 0,
		(double)width / view->current.width,
		(double)height / view->current.height);
	if (!wlr_render_pass_submit(pass)) {
		wlr_log(WLR_ERROR, "failed to submit render pass");
		wlr_buffer_drop(buffer);
		return NULL;
	}
	return buffer;
}

static struct scaled_font_buffer *
create_label(struct wlr_scene_tree *parent, struct view *view,
		struct window_switcher_thumbnail_theme *switcher_theme,
		const float *text_color, const float *bg_color, int y)
{
	struct buf buf = BUF_INIT;
	cycle_osd_field_set_custom(&buf, view,
		rc.window_switcher.osd.thumbnail_label_format);
	struct scaled_font_buffer *buffer =
		scaled_font_buffer_create(parent);
	scaled_font_buffer_update(buffer, buf.data,
		switcher_theme->item_width - 2 * switcher_theme->item_padding,
		&rc.font_osd, text_color, bg_color);
	buf_reset(&buf);
	wlr_scene_node_set_position(&buffer->scene_buffer->node,
		(switcher_theme->item_width - buffer->width) / 2, y);
	return buffer;
}

static bool
ignore_glow_input(struct wlr_scene_buffer *buffer, double *sx, double *sy)
{
	return false;
}

static struct cycle_osd_thumbnail_item *
create_item_scene(struct wlr_scene_tree *parent, struct view *view,
		struct cycle_osd_output *osd_output,
		struct window_switcher_thumbnail_theme *switcher_theme)
{
	struct server *server = osd_output->output->server;
	struct theme *theme = server->theme;
	bool overview = server->cycle.overview;
	int padding = theme->border_width + switcher_theme->item_padding;
	int title_y = switcher_theme->item_height - padding - switcher_theme->title_height;
	struct wlr_box thumb_bounds = {
		.x = padding,
		.y = padding,
		.width = switcher_theme->item_width - 2 * padding,
		.height = overview ? switcher_theme->item_height - 2 * padding
			: title_y - 2 * padding,
	};
	if (thumb_bounds.width <= 0 || thumb_bounds.height <= 0) {
		wlr_log(WLR_ERROR, "too small thumbnail area");
		return NULL;
	}

	struct cycle_osd_thumbnail_item *item = znew(*item);
	wl_list_append(&osd_output->items, &item->base.link);
	struct wlr_scene_tree *tree = wlr_scene_tree_create(parent);
	node_descriptor_create(&tree->node, LAB_NODE_CYCLE_OSD_ITEM, NULL, item);
	item->base.tree = tree;
	item->base.view = view;

	if (overview) {
		item->preview_bounds = thumb_bounds;
		item->glow = wlr_scene_buffer_create(tree, NULL);
		item->glow->point_accepts_input = ignore_glow_input;
		wlr_scene_node_set_enabled(&item->glow->node, false);
		item->preview = wlr_scene_buffer_create(tree, NULL);
		return item;
	}

	/* background for selected item */
	struct lab_scene_rect_options opts = {
		.border_colors = (float *[1]) { switcher_theme->item_active_border_color },
		.nr_borders = 1,
		.border_width = switcher_theme->item_active_border_width,
		.bg_color = switcher_theme->item_active_bg_color,
		.width = switcher_theme->item_width,
		.height = switcher_theme->item_height,
	};
	item->active_bg = lab_scene_rect_create(tree, &opts);

	/* hitbox for mouse clicks */
	wlr_scene_rect_create(tree, switcher_theme->item_width,
		switcher_theme->item_height, (float[4]) {0});

	/* thumbnail */
	struct wlr_buffer *thumb_buffer = render_thumb(osd_output->output,
		view, view->current.width, view->current.height);
	if (thumb_buffer) {
		struct wlr_scene_buffer *thumb_scene_buffer =
			wlr_scene_buffer_create(tree, thumb_buffer);
		wlr_buffer_drop(thumb_buffer);
		struct wlr_box thumb_box = box_fit_within(
			thumb_buffer->width, thumb_buffer->height,
			&thumb_bounds);
		wlr_scene_buffer_set_dest_size(thumb_scene_buffer,
			thumb_box.width, thumb_box.height);
		wlr_scene_node_set_position(&thumb_scene_buffer->node,
			thumb_box.x, thumb_box.y);
	}

	/* title */
	item->normal_label = create_label(tree, view, switcher_theme,
		theme->osd_label_text_color, theme->osd_bg_color, title_y);
	item->active_label = create_label(tree, view, switcher_theme,
		theme->osd_label_text_color, switcher_theme->item_active_bg_color, title_y);

	/* icon */
	int icon_size = switcher_theme->item_icon_size;
	struct scaled_icon_buffer *icon_buffer =
		scaled_icon_buffer_create(tree, server, icon_size, icon_size);
	scaled_icon_buffer_set_view(icon_buffer, view);
	int x = (switcher_theme->item_width - icon_size) / 2;
	int y = title_y - padding - icon_size + 10;
	wlr_scene_node_set_position(&icon_buffer->scene_buffer->node, x, y);

	return item;
}

static void
get_items_geometry(struct output *output, int nr_thumbs,
		int *nr_cols, int *nr_rows, int *nr_visible_rows)
{
	struct theme *theme = output->server->theme;
	struct window_switcher_thumbnail_theme *switcher_theme =
		&theme->osd_window_switcher_thumbnail;
	int output_width, output_height;
	wlr_output_effective_resolution(output->wlr_output,
		&output_width, &output_height);
	int padding = theme->osd_border_width + switcher_theme->padding;

	int max_bg_width = switcher_theme->max_width;
	if (switcher_theme->max_width_is_percent) {
		max_bg_width = output_width * switcher_theme->max_width / 100;
	}

	*nr_rows = 1;
	*nr_cols = nr_thumbs;
	while (1) {
		assert(*nr_rows <= nr_thumbs);
		int bg_width = *nr_cols * switcher_theme->item_width + 2 * padding;
		if (bg_width < max_bg_width) {
			break;
		}
		if (*nr_rows >= nr_thumbs) {
			break;
		}
		(*nr_rows)++;
		*nr_cols = ceilf((float)nr_thumbs / *nr_rows);
	}

	*nr_visible_rows = MIN(*nr_rows,
		(output_height - 2 * padding) / switcher_theme->item_height);
}


/* Look for commits anywhere in the window, including Wayland subsurfaces. */
static uint64_t
preview_revision(struct wlr_scene_node *node, uint64_t revision,
		const struct timespec *now)
{
	uint32_t position[] = { node->x, node->y, node->enabled };
	for (size_t i = 0; i < sizeof(position) / sizeof(*position); ++i) {
		revision = (revision ^ position[i]) * UINT64_C(1099511628211);
	}
	if (!node->enabled) {
		return revision;
	}
	if (node->type == WLR_SCENE_NODE_TREE) {
		struct wlr_scene_tree *tree = wlr_scene_tree_from_node(node);
		struct wlr_scene_node *child;
		wl_list_for_each(child, &tree->children, link) {
			revision = preview_revision(child, revision, now);
		}
	} else if (node->type == WLR_SCENE_NODE_BUFFER) {
		struct wlr_scene_buffer *buffer = wlr_scene_buffer_from_node(node);
		struct wlr_scene_surface *surface = wlr_scene_surface_try_from_buffer(buffer);
		revision = (revision ^ (uintptr_t)buffer->buffer) * UINT64_C(1099511628211);
		if (surface) {
			revision = (revision ^ surface->surface->current.seq)
				* UINT64_C(1099511628211);
			/* A visible preview may be the only presentation of this surface. */
			if (!buffer->primary_output) {
				wlr_surface_send_frame_done(surface->surface, now);
			}
		}
	}
	return revision;
}

static void
update_overview_glow(struct cycle_osd_thumbnail_item *item, bool enabled)
{
	struct wlr_scene_buffer *preview = item->preview;
	struct wlr_scene_buffer *glow = item->glow;
	bool show = enabled && preview->buffer;
	wlr_scene_node_set_enabled(&glow->node, show);
	if (!show) {
		return;
	}

	const int radius = 20;
	int width = preview->dst_width + 2 * radius;
	int height = preview->dst_height + 2 * radius;
	if (glow->dst_width != width || glow->dst_height != height || !glow->buffer) {
		/* Cache a small texture. Only a selected window needs a glow. */
		int cols = (width + 2) / 3;
		int rows = (height + 2) / 3;
		uint32_t *pixels = calloc((size_t)cols * rows, sizeof(*pixels));
		if (!pixels) {
			wlr_scene_node_set_enabled(&glow->node, false);
			return;
		}
		for (int y = 0; y < rows; ++y) {
			double py = (y + .5) * height / rows;
			double dy = MAX(0, MAX(radius - py, py - (height - radius)));
			for (int x = 0; x < cols; ++x) {
				double px = (x + .5) * width / cols;
				double dx = MAX(0, MAX(radius - px, px - (width - radius)));
				if (dx == 0 && dy == 0) {
					continue;
				}
				double distance = sqrt(dx * dx + dy * dy) / radius;
				double fade = MAX(0, 1 - distance);
				uint32_t alpha = (uint32_t)(220 * fade * fade);
				pixels[y * cols + x] = alpha * UINT32_C(0x01010101);
			}
		}
		struct lab_data_buffer *buffer = buffer_create_from_data(pixels, cols, rows,
			cols * sizeof(*pixels));
		wlr_scene_buffer_set_buffer(glow, &buffer->base);
		wlr_scene_buffer_set_dest_size(glow, width, height);
		wlr_scene_buffer_set_filter_mode(glow, WLR_SCALE_FILTER_BILINEAR);
		wlr_buffer_drop(&buffer->base);
	}
	wlr_scene_node_set_position(&glow->node, preview->node.x - radius,
		preview->node.y - radius);
}

static int
refresh_overview(void *data)
{
	struct cycle_osd_output *osd_output = data;
	struct timespec now;
	clock_gettime(CLOCK_MONOTONIC, &now);
	struct cycle_osd_thumbnail_item *item;
	wl_list_for_each(item, &osd_output->items, base.link) {
		struct view *view = item->base.view;
		if (!item->base.tree->node.enabled || !view->content_tree
				|| view->current.width <= 0 || view->current.height <= 0
				|| !view->surface || !wlr_surface_has_buffer(view->surface)) {
			continue;
		}
		uint64_t revision = preview_revision(&view->content_tree->node,
			UINT64_C(14695981039346656037), &now);
		if (item->preview->buffer && item->last_revision == revision) {
			continue;
		}
		struct wlr_box fit = box_fit_within(view->current.width,
			view->current.height, &item->preview_bounds);
		struct wlr_buffer *buffer = render_thumb(osd_output->output,
			view, fit.width, fit.height);
		if (!buffer) {
			continue;
		}
		wlr_scene_buffer_set_buffer(item->preview, buffer);
		wlr_buffer_drop(buffer);
		wlr_scene_buffer_set_dest_size(item->preview, fit.width, fit.height);
		wlr_scene_node_set_position(&item->preview->node, fit.x, fit.y);
		struct cycle_state *cycle = &osd_output->output->server->cycle;
		update_overview_glow(item, cycle->overview_arrow_used && view == cycle->selected_view);
		item->last_revision = revision;
	}
	wl_event_source_timer_update(osd_output->refresh, 83);
	return 0;
}

static void
create_overview(struct cycle_osd_output *osd_output)
{
	struct output *output = osd_output->output;
	struct server *server = output->server;
	struct wlr_box box;
	wlr_output_layout_get_box(server->output_layout, output->wlr_output, &box);
	wlr_scene_node_set_position(&osd_output->tree->node, box.x, box.y);
	overview_backdrop_create(osd_output, &box);

	int count = wl_list_length(&server->cycle.views);
	if (count) {
		const int gap = 16;
		const int margin = 36;
		int usable_width = MAX(1, box.width - margin * 2);
		int usable_height = MAX(1, box.height - 115 - margin * 2);
		int max_columns = MAX(1, MIN(5, usable_width / 228));
		int columns = MIN(max_columns, MAX(1, ceil(sqrt(count *
			(double)usable_width / usable_height * .65))));
		int rows = (count + columns - 1) / columns;
		int visible_rows = MIN(rows, MAX(1, usable_height / 180));
		int width = MAX(42, MIN(1000, (usable_width - (columns - 1) * gap) / columns));
		int height = MAX(52, MIN(width * 3 / 4,
			(usable_height - (visible_rows - 1) * gap) / visible_rows));
		int grid_height = visible_rows * (height + gap) - gap;
		int top = margin + MAX(0, (usable_height - grid_height) / 2);
		struct window_switcher_thumbnail_theme style = {
			.item_width = width, .item_height = height, .item_padding = 8,
			.item_active_border_color = {.86, .86, .86, .9},
			.item_active_bg_color = {.25, .25, .25, .5},
		};
		struct view *view;
		int i = 0;
		wl_list_for_each(view, &server->cycle.views, cycle_link) {
			int in_row = MIN(columns, count - (i / columns) * columns);
			int row_width = in_row * (width + gap) - gap;
			struct cycle_osd_thumbnail_item *item = create_item_scene(
				osd_output->items_tree, view, osd_output, &style);
			if (!item) {
				break;
			}
			wlr_scene_node_set_position(&item->base.tree->node,
				(box.width - row_width) / 2 + (i % columns) * (width + gap),
				top + (i / columns) * (height + gap));
			++i;
		}
		struct wlr_box bar = {
			.x = box.width - margin / 2, .y = top,
			.width = 4, .height = grid_height,
		};
		if (i == count) {
			cycle_osd_scroll_init(osd_output, bar, height + gap, columns, rows, visible_rows,
				style.item_active_border_color, style.item_active_bg_color);
		}
		osd_output->refresh = wl_event_loop_add_timer(
			wl_display_get_event_loop(server->wl_display), refresh_overview, osd_output);
		if (osd_output->refresh) {
			wl_event_source_timer_update(osd_output->refresh, 1);
		}
	} else {
		struct scaled_font_buffer *label = scaled_font_buffer_create(osd_output->tree);
		scaled_font_buffer_update(label, "No open windows", MAX(1, box.width - 48),
			&rc.font_osd, (float[4]){.95, .96, 1, 1}, (float[4]){0});
		wlr_scene_node_set_position(&label->scene_buffer->node,
			(box.width - label->width) / 2, (box.height - label->height) / 2);
	}
	overview_dock_create(osd_output, &box);
}

static void
cycle_osd_thumbnail_init(struct cycle_osd_output *osd_output)
{
	struct output *output = osd_output->output;
	struct server *server = output->server;
	struct theme *theme = server->theme;
	struct window_switcher_thumbnail_theme *switcher_theme =
		&theme->osd_window_switcher_thumbnail;
	int padding = theme->osd_border_width + switcher_theme->padding;

	osd_output->tree = wlr_scene_tree_create(output->cycle_osd_tree);
	osd_output->items_tree = wlr_scene_tree_create(osd_output->tree);
	if (server->cycle.overview) {
		create_overview(osd_output);
		return;
	}

	int nr_views = wl_list_length(&server->cycle.views);
	assert(nr_views > 0);
	int nr_cols, nr_rows, nr_visible_rows;
	get_items_geometry(output, nr_views, &nr_cols, &nr_rows, &nr_visible_rows);

	/* items */
	struct view *view;
	int index = 0;
	wl_list_for_each(view, &server->cycle.views, cycle_link) {
		struct cycle_osd_thumbnail_item *item = create_item_scene(
			osd_output->items_tree, view, osd_output, switcher_theme);
		if (!item) {
			break;
		}
		int x = (index % nr_cols) * switcher_theme->item_width + padding;
		int y = (index / nr_cols) * switcher_theme->item_height + padding;
		wlr_scene_node_set_position(&item->base.tree->node, x, y);
		index++;
	}

	int items_width = switcher_theme->item_width * nr_cols;
	int items_height = switcher_theme->item_height * nr_visible_rows;

	struct wlr_box scrollbar_area = {
		.x = padding + items_width - SCROLLBAR_W,
		.y = padding,
		.width = SCROLLBAR_W,
		.height = items_height,
	};
	cycle_osd_scroll_init(osd_output, scrollbar_area,
		switcher_theme->item_height, nr_cols, nr_rows, nr_visible_rows,
		switcher_theme->item_active_border_color,
		switcher_theme->item_active_bg_color);

	/* background */
	struct lab_scene_rect_options bg_opts = {
		.border_colors = (float *[1]) { theme->osd_border_color },
		.nr_borders = 1,
		.border_width = theme->osd_border_width,
		.bg_color = theme->osd_bg_color,
		.width = items_width + 2 * padding,
		.height = items_height + 2 * padding,
	};
	struct lab_scene_rect *bg =
		lab_scene_rect_create(osd_output->tree, &bg_opts);
	wlr_scene_node_lower_to_bottom(&bg->tree->node);

	/* center */
	struct wlr_box output_box;
	wlr_output_layout_get_box(server->output_layout, output->wlr_output,
		&output_box);
	int lx = output_box.x + (output_box.width - bg_opts.width) / 2;
	int ly = output_box.y + (output_box.height - bg_opts.height) / 2;
	wlr_scene_node_set_position(&osd_output->tree->node, lx, ly);
}

static void
cycle_osd_thumbnail_update(struct cycle_osd_output *osd_output)
{
	struct server *server = osd_output->output->server;
	cycle_osd_scroll_update(osd_output);

	struct cycle_osd_thumbnail_item *item;
	wl_list_for_each(item, &osd_output->items, base.link) {
		bool active = item->base.view == server->cycle.selected_view;
		if (server->cycle.overview) {
			update_overview_glow(item, active && server->cycle.overview_arrow_used);
			continue;
		}
		wlr_scene_node_set_enabled(&item->active_bg->tree->node, active);
		wlr_scene_node_set_enabled(&item->active_label->scene_buffer->node, active);
		wlr_scene_node_set_enabled(&item->normal_label->scene_buffer->node, !active);
	}
}

struct cycle_osd_impl cycle_osd_thumbnail_impl = {
	.init = cycle_osd_thumbnail_init,
	.update = cycle_osd_thumbnail_update,
};

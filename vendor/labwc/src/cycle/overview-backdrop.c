// SPDX-License-Identifier: GPL-2.0-only
#include <drm_fourcc.h>
#include <stdlib.h>
#include <wlr/render/allocator.h>
#include <wlr/render/swapchain.h>
#include <wlr/types/wlr_scene.h>
#include <wlr/util/transform.h>
#include "buffer.h"
#include "common/macros.h"
#include "cycle.h"
#include "labwc.h"
#include "output.h"

/* A separable box blur. Extend the edges so bright borders don't darken. */
static void
blur_axis(uint32_t *dst, const uint32_t *src, int length, int lines,
		int step, int line_step)
{
	const int radius = 3;
	const int diameter = radius * 2 + 1;
	for (int line = 0; line < lines; ++line) {
		const uint32_t *in = src + line * line_step;
		uint32_t *out = dst + line * line_step;
		int red = 0, green = 0, blue = 0;
		for (int offset = -radius; offset <= radius; ++offset) {
			uint32_t sample = in[MIN(MAX(offset, 0), length - 1) * step];
			red += (sample >> 16) & 255;
			green += (sample >> 8) & 255;
			blue += sample & 255;
		}
		for (int x = 0; x < length; ++x) {
			out[x * step] = UINT32_C(0xff000000) | ((red / diameter) << 16)
				| ((green / diameter) << 8) | (blue / diameter);
			uint32_t prev = in[MAX(0, x - radius) * step];
			uint32_t next = in[MIN(x + radius + 1, length - 1) * step];
			red += (int)((next >> 16) & 255) - (int)((prev >> 16) & 255);
			green += (int)((next >> 8) & 255) - (int)((prev >> 8) & 255);
			blue += (int)(next & 255) - (int)(prev & 255);
		}
	}
}

static struct wlr_buffer *
snapshot_blur(struct output *output, const struct wlr_box *box)
{
	struct wlr_swapchain *swapchain = output->wlr_output->swapchain;
	if (!output->overview_source || !swapchain) {
		return NULL;
	}
	struct server *server = output->server;
	int width = MAX(1, (box->width + 7) / 8);
	int height = MAX(1, (box->height + 7) / 8);
	struct wlr_texture *source =
		wlr_texture_from_buffer(server->renderer, output->overview_source);
	if (!source) {
		return NULL;
	}
	struct wlr_buffer *small = wlr_allocator_create_buffer(server->allocator,
		width, height, &swapchain->format);
	if (!small) {
		wlr_texture_destroy(source);
		return NULL;
	}
	struct wlr_render_pass *pass = wlr_renderer_begin_buffer_pass(
		server->renderer, small, NULL);
	bool rendered = false;
	if (pass) {
		wlr_render_pass_add_texture(pass, &(struct wlr_render_texture_options) {
			.texture = source,
			.dst_box = { .width = width, .height = height },
			.transform = wlr_output_transform_invert(output->overview_source_transform),
			.filter_mode = WLR_SCALE_FILTER_BILINEAR,
			.blend_mode = WLR_RENDER_BLEND_MODE_NONE,
		});
		rendered = wlr_render_pass_submit(pass);
	}
	wlr_texture_destroy(source);
	struct wlr_texture *texture = rendered
		? wlr_texture_from_buffer(server->renderer, small) : NULL;
	if (!texture) {
		wlr_buffer_drop(small);
		return NULL;
	}
	size_t bytes = (size_t)width * height * sizeof(uint32_t);
	uint32_t *pixels = malloc(bytes);
	bool copied = pixels && wlr_texture_read_pixels(texture,
		&(struct wlr_texture_read_pixels_options) {
			.data = pixels,
			.stride = width * sizeof(uint32_t),
			.format = DRM_FORMAT_XRGB8888,
		});
	wlr_texture_destroy(texture);
	wlr_buffer_drop(small);
	uint32_t *scratch = copied ? malloc(bytes) : NULL;
	if (!scratch) {
		free(pixels);
		return NULL;
	}
	/* Two passes per axis soften the box kernel without blurring each frame. */
	for (int i = 0; i < 2; ++i) {
		blur_axis(scratch, pixels, width, height, 1, width);
		blur_axis(pixels, scratch, height, width, width, 1);
	}
	free(scratch);
	struct lab_data_buffer *buffer = buffer_create_from_data(pixels,
		width, height, width * sizeof(uint32_t));
	return &buffer->base;
}

void
overview_backdrop_create(struct cycle_osd_output *osd_output, const struct wlr_box *box)
{
	struct output *output = osd_output->output;
	if (!output->overview_blur) {
		output->overview_blur = snapshot_blur(output, box);
	}
	if (output->overview_blur) {
		struct wlr_scene_buffer *backdrop =
			wlr_scene_buffer_create(osd_output->tree, output->overview_blur);
		wlr_scene_buffer_set_dest_size(backdrop, box->width, box->height);
		wlr_scene_buffer_set_filter_mode(backdrop, WLR_SCALE_FILTER_BILINEAR);
		wlr_scene_node_lower_to_bottom(&backdrop->node);
	} else {
		struct wlr_scene_rect *backdrop = wlr_scene_rect_create(osd_output->tree,
			box->width, box->height, (float[4]){.08, .09, .12, 1});
		wlr_scene_node_lower_to_bottom(&backdrop->node);
	}
}

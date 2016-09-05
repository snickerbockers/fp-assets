#!/usr/bin/env python

################################################################################
#
# I choose to release this file into the public domain.
# I am not responsible for any failures of this program or damage caused by it.
# You have the right to remove this statement, but I'd prefer it if you didn't.
#     -- SnickerBockers was here, 2016
#
################################################################################

import struct
import os
import zlib
import sys
import re
import json
from PIL import Image
from getopt import getopt, GetoptError

OFFSETS_START=0x83fa
IMG_COUNT=16893
SOUND_COUNT=475
FONT_COUNT=1
SHADER_COUNT=37
FILE_COUNT=18
TYPE_SIZE_COUNT = 5

assets_file_path="Assets.dat"
assets_dir_path="Assets"

usage_string = """\
Usage: %s [ -f|--in-file=<in-file> ] [ -d|--out-dir=<out-dir> ]

in_file is a path to your Assets.dat file.  it defaults to ./Assets.dat
out_dir is a path to where you want the Assets to go.  It defaults to ./Assets

This script will exit with an error if out_dir already exists.
""" % sys.argv[0]

def write_glyph(glyph_no, cur_font_dir):
    metrics_path = os.path.join(cur_font_dir, \
                                "glyph_%d_metrics.json" % glyph_no)
    metrics_file = open(metrics_path, "r")

    metrics_data_map = json.loads(metrics_file.read())
    metrics_data_bin = struct.pack("<IffffffffII",                       \
                                   int(metrics_data_map['charcode']),    \
                                   float(metrics_data_map['x1']),        \
                                   float(metrics_data_map['y1']),        \
                                   float(metrics_data_map['x2']),        \
                                   float(metrics_data_map['y2']),        \
                                   float(metrics_data_map['advance_x']), \
                                   float(metrics_data_map['advance_y']), \
                                   float(metrics_data_map['corner_x']),  \
                                   float(metrics_data_map['corner_y']),  \
                                   int(metrics_data_map['width']),       \
                                   int(metrics_data_map['height']))

    assets_file.write(metrics_data_bin)

    w = metrics_data_map['width']
    h = metrics_data_map['height']

    if w > 0 and h > 0:
        img = Image.open(os.path.join(cur_font_dir, "glyph_%d.png" % glyph_no))
        assets_file.write(img.tobytes())



try:
    for option, value in \
        getopt(sys.argv[1:], "f:d:", ["in-file=", "out-dir="])[0]:
        if option == "-f" or option == "--in-file":
            assets_file_path = value
        elif option == "-d" or option == "--out-dir":
            assets_dir_path = value
except GetoptError:
    print usage_string
    exit(1)

img_dir = os.path.join(assets_dir_path, "images")
audio_dir = os.path.join(assets_dir_path, "audio")
shader_dir = os.path.join(assets_dir_path, "shaders")
file_dir = os.path.join(assets_dir_path, "files")
font_dir = os.path.join(assets_dir_path, "fonts")

preload_file_path = os.path.join(assets_dir_path, "preload_data.bin")
type_sizes_path = os.path.join(assets_dir_path, "type_sizes.txt")

assets_file = open(assets_file_path, "wb")

preload_file = open(preload_file_path, "rb")
preload_data = preload_file.read()
preload_file.close()

assets_file.write(preload_data)
assert assets_file.tell() == OFFSETS_START

offset_block_size = 4 * (IMG_COUNT + SOUND_COUNT + FONT_COUNT \
                         + SHADER_COUNT + FILE_COUNT + TYPE_SIZE_COUNT)
assets_file.seek(OFFSETS_START + offset_block_size, os.SEEK_SET)

img_offsets = []
for img_idx in range(IMG_COUNT):
    img_offsets.append(assets_file.tell())

    img = Image.open(os.path.join(img_dir, "img_%d.png" % img_idx), "r")
    img_w, img_h = img.size
    data = zlib.compress(img.tobytes(), 9)
    img_meta_file = open(os.path.join(img_dir, \
                                      "img_%d_meta.txt" % img_idx), "r")
    img_meta_txt = img_meta_file.read().splitlines()
    img_meta_data = struct.pack("<HHHH", \
                                int(img_meta_txt[0], 0), \
                                int(img_meta_txt[1], 0), \
                                int(img_meta_txt[2], 0), \
                                int(img_meta_txt[3], 0))
    assets_file.write(struct.pack("<HH", img_w, img_h))
    assets_file.write(img_meta_data)
    assets_file.write(struct.pack("<I", len(data)))
    assets_file.write(data)


sound_offsets = []
for sound_idx in range(SOUND_COUNT):
    sound_offsets.append(assets_file.tell())

    sound_meta_file = open(os.path.join(audio_dir, \
                                        "audio_%d_meta.txt" % sound_idx), "r")
    sound_meta_txt = sound_meta_file.read().splitlines()
    sound_meta_data = struct.pack("BBBB",
                                  int(sound_meta_txt[0], 0), \
                                  int(sound_meta_txt[1], 0), \
                                  int(sound_meta_txt[2], 0), \
                                  int(sound_meta_txt[3], 0))
    sound_file = open(os.path.join(audio_dir, "audio_%d.ogg" % sound_idx), "r")
    sound_data = sound_file.read()

    assets_file.write(sound_meta_data)
    assets_file.write(struct.pack("<I", len(sound_data)))
    assets_file.write(sound_data)


font_offsets = []
for font_idx in range(FONT_COUNT):
    font_offsets.append(assets_file.tell())

    n_fonts = 0
    for file_name in os.listdir(font_dir):
        if re.match("font_\d", file_name):
            n_fonts += 1

    assets_file.write(struct.pack("<I", n_fonts))

    for font_no in range(n_fonts):
        cur_font_dir = os.path.join(font_dir, "font_%d" % font_no)
        font_meta_file = open(os.path.join(cur_font_dir, \
                                           "font_metrics.json"), "r")
        metrics_data_map = json.loads(font_meta_file.read())
        metrics_data_bin = struct.pack("<HHffffI",                         \
                                       int(metrics_data_map['size']),      \
                                       int(metrics_data_map['flags']),     \
                                       float(metrics_data_map['width']),   \
                                       float(metrics_data_map['height']),  \
                                       float(metrics_data_map['ascent']),  \
                                       float(metrics_data_map['descent']), \
                                       int(metrics_data_map['glyph_count']))
        assets_file.write(metrics_data_bin)
        for glyph_no in range(metrics_data_map['glyph_count']):
            write_glyph(glyph_no, cur_font_dir)


shader_offsets = []
for shader_idx in range(SHADER_COUNT):
    shader_offsets.append(assets_file.tell())

    shader_file = open(os.path.join(shader_dir, \
                                    "shader_%d_vert.glsl" % shader_idx), "r")
    shader_txt = shader_file.read()
    shader_len = struct.pack("<I", len(shader_txt))
    assets_file.write(shader_len)
    assets_file.write(shader_txt)

    shader_file = open(os.path.join(shader_dir, \
                                    "shader_%d_frag.glsl" % shader_idx), "r")
    shader_txt = shader_file.read()
    shader_len = struct.pack("<I", len(shader_txt))
    assets_file.write(shader_len)
    assets_file.write(shader_txt)

file_offsets = []
for file_idx in range(FILE_COUNT):
    file_offsets.append(assets_file.tell())

    file_file = open(os.path.join(file_dir, "file_%d.txt" % file_idx), "r")
    file_txt = file_file.read()
    file_len = struct.pack("<I", len(file_txt))
    assets_file.write(file_len)
    assets_file.write(file_txt)

# read in the type sizes
type_sizes = []
type_size_file = open(type_sizes_path, "r")
type_size_txt = type_size_file.read().splitlines()
for i in range(TYPE_SIZE_COUNT):
    ts = int(type_size_txt[i], 0)
    type_sizes.append(ts)

# now write the offsets block and the type sizes
assets_file.seek(OFFSETS_START, os.SEEK_SET)
for offset in (img_offsets + sound_offsets + font_offsets + \
               shader_offsets + file_offsets + type_sizes):
    assets_file.write(struct.pack("<I", offset))

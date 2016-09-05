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

img_offsets = []
sound_offsets = []
font_offsets = []
shader_offsets = []
file_offsets = []
type_sizes = []

img_dir = None
audio_dir = None
shader_dir = None
file_dir = None
font_dir = None

preload_file_path = None
type_sizes_path = None

usage_string = """\
Usage: %s [ -f|--in-file=<in-file> ] [ -d|--out-dir=<out-dir> ]

in_file is a path to your Assets.dat file.  it defaults to ./Assets.dat
out_dir is a path to where you want the Assets to go.  It defaults to ./Assets

This script will exit with an error if out_dir already exists.
""" % sys.argv[0]

def extract_glyph(assets_file, metrics_path, img_path):
    """
    reads in a glyph from assets_file and saves the metrics
    to a json and the glyph itself to a png.

    metrics_path is the name of the file that will hold the metrics.
    img_path is the name of the file that will hold the image.
    """
    metrics = { }
    metrics['charcode'], = struct.unpack("<I", assets_file.read(4))
    metrics['x1'], = struct.unpack("<f", assets_file.read(4))
    metrics['y1'], = struct.unpack("<f", assets_file.read(4))
    metrics['x2'], = struct.unpack("<f", assets_file.read(4))
    metrics['y2'], = struct.unpack("<f", assets_file.read(4))
    metrics['advance_x'], = struct.unpack("<f", assets_file.read(4))
    metrics['advance_y'], = struct.unpack("<f", assets_file.read(4))
    metrics['corner_x'], = struct.unpack("<f", assets_file.read(4))
    metrics['corner_y'], = struct.unpack("<f", assets_file.read(4))
    metrics['width'], = struct.unpack("<I", assets_file.read(4))
    metrics['height'], = struct.unpack("<I", assets_file.read(4))

    metrics_file = open(metrics_path, "w")
    metrics_file.write(json.dumps(metrics))

    w = metrics['width']
    h = metrics['height']

    if w > 0 and h > 0:
        raw_img = assets_file.read(w * h)
        out_img = Image.frombytes("L", (w, h), raw_img)
        out_img.save(img_path)

def extract_font(assets_file, cur_font_dir):
    """
    reads a font in from assets_file, saves the metrics to a json,
    and then calls read_glyph for each glyph in the font.
    All font-data will be saved under cur_font_dir.
    assets_file should be seek'd to the beginning of the font data before
    calling this function.
    """
    os.mkdir(cur_font_dir, 0755)

    font_metrics = {}
    font_metrics['size'], = struct.unpack("<H", assets_file.read(2))
    font_metrics['flags'], = struct.unpack("<H", assets_file.read(2))
    font_metrics['width'],  = struct.unpack("<f", assets_file.read(4))
    font_metrics['height'], = struct.unpack("<f", assets_file.read(4))
    font_metrics['ascent'], = struct.unpack("<f", assets_file.read(4))
    font_metrics['descent'], = struct.unpack("<f", assets_file.read(4))
    font_metrics['glyph_count'], = struct.unpack("<I", assets_file.read(4))

    metrics_file = open(os.path.join(cur_font_dir, \
                                     "font_metrics.json"), "w")
    metrics_file.write(json.dumps(font_metrics))
    for glyph_no in range(font_metrics['glyph_count']):
        glyph_metrics_path = os.path.join(cur_font_dir, \
                                          "glyph_%d_metrics.json" % glyph_no)
        glyph_img_path = os.path.join(cur_font_dir, "glyph_%d.png" % glyph_no)
        extract_glyph(assets_file, metrics_path=glyph_metrics_path, \
                      img_path=glyph_img_path)

# Format of images in Assets.dat:
#     width (16 bits)
#     height (16 bits)
#     The four mystery integers (16 bits * 4)
#     Compressed file length (32-bits)
#     Truecolor RGBA quads compressed using the deflate/zlib format.
#
# These are all little-endian values.
def extract_img(assets_file, out_img_path, out_meta_path):
    """
    extract an image from assets_file.  The image will be saved in out_img_path
    and the metadata (excluding the image resolution) will be saved as text to
    out_meta_path.  assets_file's stream position should already point to the
    beginning of the data (image width) before calling this function.
    """
    img_w = struct.unpack("<H", assets_file.read(2))[0]
    img_h = struct.unpack("<H", assets_file.read(2))[0]

    # After the image dimensions there are 4 16-bit integers.
    # I do not know what these represent, so I save them to a text file
    # so they'll be around later when we build a new Assets.dat
    meta_txt = open(os.path.join(img_dir, out_meta_path), "w")
    for i in range(4):
        meta_txt.write("0x%x\n" % struct.unpack("<H", assets_file.read(2))[0])

    file_len = struct.unpack("<I", assets_file.read(4))[0]
    file_dat = zlib.decompress(assets_file.read(file_len))

    out_img = Image.frombytes("RGBA", (img_w, img_h), file_dat)
    out_img.save(os.path.join(img_dir, out_img_path))

def extract_text(assets_file, out_file_path):
    """
    extract a text file from assets_file.
    out_file_path is the path to where the text should be saved.
    assets_file should already be seek'd to the 4-byte length that
    precede's the text.
    """
    file_len = struct.unpack("<I", assets_file.read(4))[0]
    file_dat = assets_file.read(file_len)
    out_file = open(out_file_path,"w")
    out_file.write(file_dat)

def init_paths(assets_dir_path):
    """
    if you're importing fp-assets as a library and you're not calling
    extract_all_assets, you have to call this function before doing anything
    else to initialize some global variables.
    """
    global img_dir, audio_dir, shader_dir, file_dir, \
        font_dir, preload_file_path, type_sizes_path
    img_dir = os.path.join(assets_dir_path, "images")
    audio_dir = os.path.join(assets_dir_path, "audio")
    shader_dir = os.path.join(assets_dir_path, "shaders")
    file_dir = os.path.join(assets_dir_path, "files")
    font_dir = os.path.join(assets_dir_path, "fonts")

    preload_file_path = os.path.join(assets_dir_path, "preload_data.bin")
    type_sizes_path = os.path.join(assets_dir_path, "type_sizes.txt")

def extract_all_assets(assets_file_path, assets_dir_path):
    init_paths(assets_dir_path)
    assets_file = open(assets_file_path, "rb")

    os.mkdir(assets_dir_path, 0755)
    os.mkdir(img_dir, 0755)
    os.mkdir(audio_dir, 0755)
    os.mkdir(shader_dir, 0755)
    os.mkdir(file_dir, 0755)
    os.mkdir(font_dir, 0755)

    # read in the preload data.  I don't know what to do with this other than
    # to hold onto it.
    preload_data = assets_file.read(OFFSETS_START)
    preload_data_file = open(preload_file_path, "w")
    preload_data_file.write(preload_data)

    # read in image offsets
    for i in range(IMG_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        img_offsets.append(offset)

    # read in sound offsets
    for i in range(SOUND_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        sound_offsets.append(offset)

    # read in the font offsets
    for i in range(FONT_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        font_offsets.append(offset)

    # read in the shader offsets
    for i in range(SHADER_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        shader_offsets.append(offset)

    # read in the file offsets
    for i in range(FILE_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        file_offsets.append(offset)

    for i in range(TYPE_SIZE_COUNT):
        ts = struct.unpack("<I", assets_file.read(4))[0]
        type_sizes.append(ts)

    # write the type sizes
    type_size_file = open(type_sizes_path, "w")
    for ts in type_sizes:
        type_size_file.write("0x%x\n" % ts)

    for index, offset in enumerate(img_offsets):
        assets_file.seek(offset)
        extract_img(assets_file, "img_%d.png" % index, \
                    "img_%d_meta.txt" % index)

    for index, offset in enumerate(sound_offsets):
        assets_file.seek(offset)

        # Here there are 4 unknown bytes followed by a 4-byte length and then
        # an ogg file
        meta_txt = open(os.path.join(audio_dir, \
                                     "audio_%d_meta.txt" % index), "w")
        for i in range(4):
            meta_txt.write("0x%x\n" % struct.unpack("B", assets_file.read(1))[0])

        file_len = struct.unpack("<I", assets_file.read(4))[0]
        file_dat = assets_file.read(file_len)
        out_file = open(os.path.join(audio_dir, "audio_%d.ogg" % index), "w")
        out_file.write(file_dat)

    # next read in fonts
    for index, offset in enumerate(font_offsets):
        assets_file.seek(offset)

        n_fonts = struct.unpack("<I", assets_file.read(4))[0]

        for font_no in range(n_fonts):
            extract_font(assets_file, \
                         os.path.join(font_dir, "font_%d" % font_no))

    # next read in shaders.  These are just 4-byte lengths followed by text
    for index, offset in enumerate(shader_offsets):
        assets_file.seek(offset)
        extract_text(assets_file, os.path.join(shader_dir, \
                                               "shader_%d_vert.glsl" % index))
        extract_text(assets_file, os.path.join(assets_dir_path, "shaders", \
                                               "shader_%d_frag.glsl" % index))

    # next read in files.  These are just 4-byte lengths followed by text.
    for index, offset in enumerate(file_offsets):
        assets_file.seek(offset)
        extract_text(assets_file, os.path.join(assets_dir_path, "files", \
                                               "file_%d.txt" % index))
if __name__ == "__main__":
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

    if os.path.exists(assets_dir_path):
        print "Error: \"%s\" already exists" % assets_dir_path
        exit(1)

    extract_all_assets(assets_file_path=assets_file_path, \
                       assets_dir_path=assets_dir_path)

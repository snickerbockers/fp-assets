#!/bin/env python

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
from PIL import Image
from getopt import getopt, GetoptError

OFFSETS_START=0x83fa
IMG_COUNT=16893
SOUND_COUNT=475
FONT_COUNT=1
SHADER_COUNT=37
FILE_COUNT=18

assets_file_path="Assets.dat"
assets_dir_path="Assets"

usage_string = """\
Usage: %s [ -f|--in-file=<in-file> ] [ -d|--out-dir=<out-dir> ]

in_file is a path to your Assets.dat file.  it defaults to ./Assets.dat
out_dir is a path to where you want the Assets to go.  It defaults to ./Assets

This script will exit with an error if out_dir already exists.
""" % sys.argv[0]


try:
    for option, value in \
        getopt(sys.argv[1:], "f:d:", ["in-file=", "out-file="])[0]:
        if option == "-f" or option == "--in-file":
            assets_file_path = value
        elif option == "-d" or option == "--out-file":
            assets_dir_path = value
except GetoptError:
    print usage_string
    exit(1)

if os.path.exists(assets_dir_path):
    print "Error: \"%s\" already exists" % assets_dir_path
    exit(1)

assets_file = open(assets_file_path, "rb")

img_offsets = []
sound_offsets = []
font_offsets = []
shader_offsets = []
file_offsets = []
type_sizes = []

assets_file.seek(OFFSETS_START)

os.mkdir(assets_dir_path, 0755)
os.mkdir(os.path.join(assets_dir_path, "images"), 0755)
os.mkdir(os.path.join(assets_dir_path, "audio"), 0755)
os.mkdir(os.path.join(assets_dir_path, "shaders"), 0755)
os.mkdir(os.path.join(assets_dir_path, "files"), 0755)

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

# Format of images in Assets.dat:
#     width (16 bits)
#     height (16 bits)
#     The four mystery integers (16 bits * 4)
#     Compressed file length (32-bits)
#     Truecolor RGBA quads compressed using the deflate/zlib format.
#
# These are all little-endian values.
for index, offset in enumerate(img_offsets):
    assets_file.seek(offset)

    img_w = struct.unpack("<H", assets_file.read(2))[0]
    img_h = struct.unpack("<H", assets_file.read(2))[0]

    # After the image dimensions there are 4 16-bit integers.
    # I do not know what these represent, so I save them to a text file
    # so they'll be around later when we build a new Assets.dat
    meta_txt = open(os.path.join(assets_dir_path, "images", \
                                 "img_%d_meta.txt" % index), "w")
    for i in range(4):
        meta_txt.write("0x%x\n" % struct.unpack("<H", assets_file.read(2))[0])

    file_len = struct.unpack("<I", assets_file.read(4))[0]
    file_dat = zlib.decompress(assets_file.read(file_len))

    out_img = Image.frombytes("RGBA", (img_w, img_h), file_dat)
    out_img.save(os.path.join(assets_dir_path, "images", "img_%d.png" % index))

for index, offset in enumerate(sound_offsets):
    assets_file.seek(offset)

    # Here there are 4 unknown bytes followed by a 4-byte length and then
    # an ogg file
    meta_txt = open(os.path.join(assets_dir_path, "audio", \
                                 "audio_%d_meta.txt" % index), "w")
    for i in range(4):
        meta_txt.write("0x%x\n" % struct.unpack("B", assets_file.read(1))[0])

    file_len = struct.unpack("<I", assets_file.read(4))[0]
    file_dat = assets_file.read(file_len)
    out_file = open(os.path.join(assets_dir_path, "audio",
                                 "audio_%d.ogg" % index), "w")
    out_file.write(file_dat)

# next read in fonts
for index, offset in enumerate(font_offsets):
    print "font offset is 0x%x" % offset
    assets_file.seek(offset)

# next read in shaders.  These are just 4-byte lengths followed by text
for index, offset in enumerate(shader_offsets):
    assets_file.seek(offset)
    file_len = struct.unpack("<I", assets_file.read(4))[0]
    file_dat = assets_file.read(file_len)
    out_file = open(os.path.join(assets_dir_path, "shaders", \
                                 "shader_%d.glsl" % index), "w")
    out_file.write(file_dat)

# next read in files.  These are just 4-byte lengths followed by text.
#
# One interesting anomally here is that file_0.txt appears to be a shader.
# This could mean that SHADER_COUNT ought to be 38, but
# but I'm very confident that it's supposed to be 37.  I think this one was
# classified as a file instead of a shader because it's a fragment shader, and
# all the other shaders are vertex shaders.
for index, offset in enumerate(file_offsets):
    file_len = struct.unpack("<I", assets_file.read(4))[0]
    file_dat = assets_file.read(file_len)
    out_file = open(os.path.join(assets_dir_path, "files", \
                                 "file_%d.txt" % index), "w")
    out_file.write(file_dat)

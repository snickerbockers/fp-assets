#!/usr/bin/env python3

################################################################################
#
# contact: snickerbockers@washemu.org
#
# I choose to release this file into the public domain.
# I am not responsible for any failures of this program or damage caused by it.
# You have the right to remove this statement, but I'd prefer it if you didn't.
#     -- SnickerBockers was here, 2016, 2023
#
################################################################################

import re
import struct
import os
import zlib
import sys
import json
import hashlib
from PIL import Image
from getopt import getopt, GetoptError
from chowimg import load_img, compress_img

assets_file_path="Assets.dat"
assets_dir_path="Assets"

verbose = False

img_dir = None
audio_dir = None
shader_dir = None
file_dir = None
font_dir = None

preload_file_path = None
type_sizes_path = None

usage_string = """\
Usage: %s -c | -x [ -f|--file=<in-file> ] [-m metadata_file] [-r] [pathname]

in-file is a path to your Assets.dat file.  it defaults to ./Assets.dat
pathname is the path to the directory to be extracted to/created from.
    It defaults to ./Assets/

-c creates a new Assets.dat.
-x extracts Assets.dat
-m is the path to a json file describing Assets.dat metadata; this is only required if fp-assets.py cannot auto-identify your file
-r extracts images as raw "binary blobs" instead of decoding them and converting to PNG; only use this if you *absolutely* understand what you're doing.

extracting will exit with an error if pathname already exists.
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
    os.mkdir(cur_font_dir, 0o755)

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
#     32-bit RGBA image data, compressed using either zlib or a custom algorithm (see chowimg.py)
#
# These are all little-endian values.
def extract_img(assets_file, out_img_path, out_meta_path, raw_images):
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

    if raw_images:
        meta_txt.write("%ux%u\n" % (img_w,img_h))
        dat = assets_file.read(file_len)
        outfile = open(os.path.join(img_dir, out_img_path), "wb")
        outfile.write(dat)
        outfile.close()
    else:
        if image_format == 'chowdren':
            file_dat = load_img(assets_file, file_len)
        elif image_format == 'zlib':
            file_dat = zlib.decompress(assets_file.read(file_len))
        else:
            print("unknown image compression format %s" % image_format)
            exit(1)

        out_img = Image.frombytes("RGBA", (img_w, img_h), bytes(file_dat))
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
    out_file = open(out_file_path,"wb")
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

def write_glyph(assets_file, img_path, metrics_path):
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
        img = Image.open(img_path)
        assets_file.write(img.tobytes())

def write_font(assets_file, cur_font_dir):
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
        metrics_path = os.path.join(cur_font_dir, \
                                    "glyph_%d_metrics.json" % glyph_no)
        img_path = os.path.join(cur_font_dir, "glyph_%d.png" % glyph_no)
        write_glyph(assets_file, \
                    metrics_path=metrics_path, img_path=img_path)

def write_img(assets_file, img_path, meta_path):
    img = Image.open(img_path, "r")
    img_w, img_h = img.size
    if image_format == 'zlib':
        data = zlib.compress(img.tobytes(), 9)
    else:
        data = compress_img(img.tobytes())
    img_meta_file = open(meta_path, "r")
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

def write_sound(assets_file, sound_path, meta_path):
    sound_meta_file = open(meta_path, "r")
    sound_meta_txt = sound_meta_file.read().splitlines()
    sound_meta_data = struct.pack("BBBB",
                                  int(sound_meta_txt[0], 0), \
                                  int(sound_meta_txt[1], 0), \
                                  int(sound_meta_txt[2], 0), \
                                  int(sound_meta_txt[3], 0))
    sound_file = open(sound_path, "rb")
    sound_data = sound_file.read()

    assets_file.write(sound_meta_data)
    assets_file.write(struct.pack("<I", len(sound_data)))
    assets_file.write(sound_data)

def write_text(assets_file, text_file_path):
    text_file = open(text_file_path, "rb")
    text_data = text_file.read()
    text_len = struct.pack("<I", len(text_data))
    assets_file.write(text_len)
    assets_file.write(text_data)

def write_assets_file(assets_file_path, assets_dir_path):
    init_paths(assets_dir_path)
    assets_file = open(assets_file_path, "wb")

    preload_file = open(preload_file_path, "rb")
    preload_data = preload_file.read()
    preload_file.close()

    assets_file.write(preload_data)
    if assets_file.tell() != OFFSETS_START:
        raise ValueError("preload_data has a length of %d (should be %d)" % \
                         (len(preload_data), OFFSETS_START))

    offset_block_size = 4 * (IMG_COUNT + SOUND_COUNT + FONT_COUNT \
                             + SHADER_COUNT + FILE_COUNT + TYPE_SIZE_COUNT)
    assets_file.seek(OFFSETS_START + offset_block_size, os.SEEK_SET)

    img_offsets = []
    for img_idx in range(IMG_COUNT):
        if verbose:
            print("now saving image %d..." % img_idx)
        img_offsets.append(assets_file.tell())

        write_img(assets_file, \
                  img_path=os.path.join(img_dir, "img_%d.png" % img_idx), \
                  meta_path=os.path.join(img_dir, "img_%d_meta.txt" % img_idx))

    sound_offsets = []
    for sound_idx in range(SOUND_COUNT):
        if verbose:
            print("now saving sound %d..." % sound_idx)
        sound_offsets.append(assets_file.tell())

        sound_path = os.path.join(audio_dir, "audio_%d.ogg" % sound_idx)
        meta_path = os.path.join(audio_dir, "audio_%d_meta.txt" % sound_idx)
        write_sound(assets_file, sound_path=sound_path, meta_path=meta_path)

    font_offsets = []
    for font_idx in range(FONT_COUNT):
        if verbose:
            print("now saving font %d..." % font_idx)
        font_offsets.append(assets_file.tell())

        n_fonts = 0
        for file_name in os.listdir(font_dir):
            if re.match("font_\d", file_name):
                n_fonts += 1

        assets_file.write(struct.pack("<I", n_fonts))

        for font_no in range(n_fonts):
            cur_font_dir = os.path.join(font_dir, "font_%d" % font_no)
            write_font(assets_file, cur_font_dir=cur_font_dir)

    shader_offsets = []
    for shader_idx in range(SHADER_COUNT):
        if verbose:
            print("now saving shader %d..." % shader_idx)
        shader_offsets.append(assets_file.tell())

        vert_path = os.path.join(shader_dir, "shader_%d_vert.glsl" % shader_idx)
        frag_path = os.path.join(shader_dir, "shader_%d_frag.glsl" % shader_idx)

        write_text(assets_file, text_file_path=vert_path)
        write_text(assets_file, text_file_path=frag_path)

    file_offsets = []
    for file_idx in range(FILE_COUNT):
        if verbose:
            print("now saving file %d..." % file_idx)
        file_offsets.append(assets_file.tell())

        file_path = os.path.join(file_dir, "file_%d.txt" % file_idx)
        write_text(assets_file, text_file_path=file_path)

    # read in the type sizes
    type_sizes = []
    type_size_file = open(type_sizes_path, "r")
    type_size_txt = type_size_file.read().splitlines()
    for i in range(TYPE_SIZE_COUNT):
        if verbose:
            print("now saving type size %d..." % i)
        ts = int(type_size_txt[i], 0)
        type_sizes.append(ts)

    if verbose:
        print("now writing metadata block...")
    # now write the offsets block and the type sizes
    assets_file.seek(OFFSETS_START, os.SEEK_SET)
    for offset in (img_offsets + sound_offsets + font_offsets + \
                   shader_offsets + file_offsets + type_sizes):
        assets_file.write(struct.pack("<I", offset))

def extract_all_assets(assets_file_path, assets_dir_path, fmt, raw_images):
    if os.path.exists(assets_dir_path):
        print("Error: \"%s\" already exists" % assets_dir_path)
        exit(1)

    init_paths(assets_dir_path)
    assets_file = open(assets_file_path, "rb")

    os.mkdir(assets_dir_path, 0o755)
    os.mkdir(img_dir, 0o755)
    os.mkdir(audio_dir, 0o755)
    os.mkdir(shader_dir, 0o755)
    os.mkdir(file_dir, 0o755)
    os.mkdir(font_dir, 0o755)

    # read in the preload data.  This doesn't seem to serve any purpose in
    # Freedom Planet and you can actually zero it out without consequence.
    # This script dumps it anyways and re-inserts it verbatim when the new
    # Assets.dat just in case I'm wrong.  At any rate, this keeps binary
    # patches small.
    preload_data = assets_file.read(OFFSETS_START)
    preload_data_file = open(preload_file_path, "wb")
    preload_data_file.write(preload_data)

    # read in image offsets
    img_offsets = []
    for i in range(IMG_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        img_offsets.append(offset)

    # read in sound offsets
    sound_offsets = []
    for i in range(SOUND_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        sound_offsets.append(offset)

    # read in the font offsets
    font_offsets = []
    for i in range(FONT_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        font_offsets.append(offset)

    # read in the shader offsets
    shader_offsets = []
    for i in range(SHADER_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        shader_offsets.append(offset)

    # read in the file offsets
    file_offsets = []
    for i in range(FILE_COUNT):
        offset = struct.unpack("<I", assets_file.read(4))[0]
        file_offsets.append(offset)

    type_sizes = []
    for i in range(TYPE_SIZE_COUNT):
        ts = struct.unpack("<I", assets_file.read(4))[0]
        type_sizes.append(ts)

    # write the type sizes
    type_size_file = open(type_sizes_path, "w")
    for ts in type_sizes:
        type_size_file.write("0x%x\n" % ts)

    if raw_images:
        img_ext = "bin"
    else:
        img_ext = "png"
    for index, offset in enumerate(img_offsets):
        assets_file.seek(offset)
        extract_img(assets_file, "img_%d.%s" % (index, img_ext), \
                    "img_%d_meta.txt" % index, raw_images)

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
        out_file = open(os.path.join(audio_dir, "audio_%d.ogg" % index), "wb")
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

    # save metadata so we have it on hand when we create a new Assets.dat
    fmt_file = open(os.path.join(assets_dir_path, "format.json"), "w")
    json.dump(fmt, fmt_file, indent=4)
    fmt_file.close()

def md5sum(path):
    hasher = hashlib.md5()
    stream = open(path, "rb")
    buf = stream.read(4096)
    while buf:
        hasher.update(buf)
        buf = stream.read(4096)
    stream.close()
    return hasher.hexdigest()


if __name__ == "__main__":
    do_extract = False
    do_compress = False
    metadata_json = None
    raw_images = False
    try:
        opt_val, params = getopt(sys.argv[1:], "xcf:m:rv", ["file="])
        for option, value in opt_val:
            if option == "-f" or option == "--in-file":
                assets_file_path = value
            elif option == "-c":
                do_compress = True
            elif option == "-x":
                do_extract = True
            elif option == "-m":
                metadata_json = value
            elif option == "-r":
                raw_images = True
            elif option == "-v":
                verbose = True
    except GetoptError:
        print(usage_string)
        exit(1)

    if len(params) == 1:
        assets_dir_path = params[0]
    elif len(params) != 0:
        print("Error: extra unparsed arguments: %s" % str(params))
        exit(1)

    if not (do_compress or do_extract):
        print("Error: need to specify either compress (-c) or extract (-x)")
        exit(1)

    if do_compress and do_extract:
        print("Error: cannot both compress (-c) and extract (-x) at the same time")
        exit(1)

    if do_extract:
        csum = md5sum(assets_file_path)
        print("assets file has a checksum of %s" % csum)
        if metadata_json is None:
            # latest version (as of may 2023).  fb95f5c is linux, 4085c98 is windows
            if csum == "fb95f5c4809e76cae933be20ca51a660" or csum == "4085c983fb918703ce459f17f69c474c":
                format_string = """
                {
                "OFFSETS_START" : 34324,
                "IMG_COUNT"  : 17162,
                "SOUND_COUNT" : 475,
                "FONT_COUNT" : 0,
                "SHADER_COUNT" : 95,
                "FILE_COUNT" : 18,
                "TYPE_SIZE_COUNT" : 5,
                "image_format" : "chowdren"
                }
                """
            elif csum == "f14f24317d0323d63231cdbba511f254":
                format_string = """
                {
                "OFFSETS_START" : 33786,
                "IMG_COUNT" : 16893,
                "SOUND_COUNT" : 475,
                "FONT_COUNT" : 1,
                "SHADER_COUNT" : 37,
                "FILE_COUNT" : 18,
                "TYPE_SIZE_COUNT" : 5,
                "image_format" : "zlib"
                }
                """
            else:
                print("unrecognized assets file with md5sum %s" % csum)
                print("you will need to supply your own metadata json files with the -m option")
                exit(1)
            print("csum %s is recognized as an official release, and its metadata is known" % csum)
        else:
            metadata_file = open(metadata_json, "r")
            format_string = metadata_file.read()
            metadata_file.close()

        fmt = json.loads(format_string)
        OFFSETS_START = int(fmt['OFFSETS_START'])
        IMG_COUNT = int(fmt['IMG_COUNT'])
        SOUND_COUNT = int(fmt['SOUND_COUNT'])
        FONT_COUNT = int(fmt['FONT_COUNT'])
        SHADER_COUNT = int(fmt['SHADER_COUNT'])
        FILE_COUNT = int(fmt['FILE_COUNT'])
        TYPE_SIZE_COUNT = int(fmt['TYPE_SIZE_COUNT'])
        image_format = fmt['image_format']

        extract_all_assets(assets_file_path=assets_file_path, \
                           assets_dir_path=assets_dir_path,
                           fmt=fmt, raw_images=raw_images)

    if do_compress:
        if metadata_json is None:
            metadata_json = os.path.join(assets_dir_path, 'format.json')
        try:
            with open(metadata_json, 'r') as meta_file:
                format_string = meta_file.read()
                fmt = json.loads(format_string)
                OFFSETS_START = int(fmt['OFFSETS_START'])
                IMG_COUNT = int(fmt['IMG_COUNT'])
                SOUND_COUNT = int(fmt['SOUND_COUNT'])
                FONT_COUNT = int(fmt['FONT_COUNT'])
                SHADER_COUNT = int(fmt['SHADER_COUNT'])
                FILE_COUNT = int(fmt['FILE_COUNT'])
                TYPE_SIZE_COUNT = int(fmt['TYPE_SIZE_COUNT'])
                image_format = fmt['image_format']
        except FileNotFoundError:
            print("ERROR: unable to open %s ; please proved path to a valid metadata json file with the -m option" % metadata_json, file = sys.stderr)
            exit(1)

        write_assets_file(assets_file_path, assets_dir_path)

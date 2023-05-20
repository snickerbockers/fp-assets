#!/usr/bin/env python3

################################################################################
#
# contact: snickerbockers@washemu.org
#
# I choose to release this file into the public domain.
# I am not responsible for any failures of this program or damage caused by it.
# You have the right to remove this statement, but I'd prefer it if you didn't.
#     -- SnickerBockers was here, 2023
#
################################################################################

import sys
import struct
from PIL import Image
from getopt import getopt, GetoptError

# stats kept for verbose (-v) mode
# i use this for debugging
hunk_count = 0

def load_vll(infile, first_nibble):
    bytes_read = 0
    vll = first_nibble
    if first_nibble == 0xf:
        latest_byte = 0xff
        while latest_byte == 0xff:
            latest_byte = struct.unpack("B", infile.read(1))[0]
            bytes_read += 1
            vll += latest_byte
    return (vll, bytes_read)


def load_hunk(infile, verbose=False):
    hunk = []

    hunk_len = struct.unpack("<I", infile.read(4))[0]

    bytes_read = 0

    while bytes_read < hunk_len:
        ctrl_byte = struct.unpack("B", infile.read(1))[0]
        bytes_read += 1

        literal_byte_count = ctrl_byte >> 4
        literal_byte_count, vll_len = load_vll(infile, ctrl_byte >> 4)
        bytes_read += vll_len

        for index in range(literal_byte_count):
            hunk.append(struct.unpack("B", infile.read(1))[0])
            bytes_read += 1

        if bytes_read >= hunk_len:
            break

        # now for the sliding window
        rewind_distance = struct.unpack("<H", infile.read(2))[0]
        window_start = len(hunk) - rewind_distance
        bytes_read += 2
        window_byte_count, vll_len = load_vll(infile, ctrl_byte & 0xf)
        window_byte_count += 4
        bytes_read += vll_len

        for index in range(window_byte_count):
            hunk.append(hunk[window_start + index])

        if verbose:
            print("\t\t%u literal bytes, %u repeat bytes starting %u from the end" % (literal_byte_count, window_byte_count, rewind_distance))

    return (hunk, bytes_read + 4)

def load_img(infile, compressed_len, verbose=False):
    img_dat = []
    total_bytes_read = 0
    hunk_count = 0
    while total_bytes_read < compressed_len:
        if verbose:
            print("begin hunk number %u" % hunk_count)
        hunk, bytes_read = load_hunk(infile, verbose)
        img_dat += hunk
        total_bytes_read += bytes_read
        hunk_count += 1
    print("total hunk count: %u" % hunk_count)

    return img_dat

if __name__=='__main__':
    usage_string="Usage: %s [-v] -x|-c <in-file> <out-file>" % sys.argv[0]

    # mode 0 - indeterminate
    # mode 1 - eXtract
    # mode 2 - Compress
    mode = 0
    width = -1
    height = -1
    verbose = False

    try:
        opt_val, params = getopt(sys.argv[1:], "xcw:h:v")
        for option, value in opt_val:
            if option == "-x":
                if mode == 2:
                    print(usage_string)
                    exit(1)
                mode = 1
            elif option == "-c":
                if mode == 1:
                    print(usage_string)
                    exit(1)
                mode = 2
            elif option == "-w":
                width = int(value)
            elif option == "-h":
                height = int(value)
            elif option == "-v":
                verbose = True
    except GetoptError:
        print(usage_string)
        exit(1)

    if len(params) != 2 or (mode != 1 and mode != 2):
        print(usage_string)
        exit(1)

    if mode == 1:
        print("extraction selected")
        if width < 0 or height < 0:
            print("WIDTH AND HEIGHT NOT INPUT; RUN WITH -w AND -h options")
            exit(1)
        print("requested dimensions are %ux%u" % (width, height))

        infile = open(params[0], "rb")

        infile.seek(0, 2)
        compressed_len = infile.tell()
        infile.seek(0)

        img_dat = load_img(infile, compressed_len, verbose)

        infile.close()
        print("total uncompressed image length is %u bytes" % len(img_dat))

        img_obj = Image.frombytes("RGBA", (width, height), bytes(img_dat))
        img_obj.save(params[1])
    elif mode == 2:
        pass
    else:
        # should be impossible to get here anyways
        print(usage_string)
        exit(1)

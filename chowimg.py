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


def load_hunk(infile, verbose=0):
    hunk = []

    hunk_len = struct.unpack("<I", infile.read(4))[0]
    if verbose:
        print("first hunk has a length of %d bytes" % hunk_len)

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

        if verbose:
            print("there are currently %d bytes decompressed" % len(hunk))

        if bytes_read >= hunk_len:
            break

        # now for the sliding window
        window_start = len(hunk) - struct.unpack("<H", infile.read(2))[0]
        bytes_read += 2
        window_byte_count, vll_len = load_vll(infile, ctrl_byte & 0xf)
        window_byte_count += 4
        bytes_read += vll_len

        if verbose:
            print("next copy %u bytes from the sliding window starting from %u" %
                  (window_byte_count, window_start))

        for index in range(window_byte_count):
            hunk.append(hunk[window_start + index])

        if verbose:
            print("hunk is now %u bytes" % len(hunk))
            print("%u bytes left to process in hunk" % (hunk_len - bytes_read))

    return (hunk, bytes_read + 4)

def load_img(infile, compressed_len):
    img_dat = []
    total_bytes_read = 0
    while total_bytes_read < compressed_len:
        hunk, bytes_read = load_hunk(infile)
        img_dat += hunk
        total_bytes_read += bytes_read
    return img_dat

if __name__=='__main__':
    usage_string="Usage: %s <in-file.bin> <out-file.png>" % sys.argv[0]

    if len(sys.argv) != 3:
        print(usage_string);
        exit(1);

    infile = open(sys.argv[1], "rb")

    infile.seek(0, 2)
    compressed_len = infile.tell()
    infile.seek(0)

    img_dat = load_img(infile, compressed_len)

    infile.close()
    print("total uncompressed image length is %u bytes" % len(img_dat))

    outfile = open(sys.argv[2], "wb")
    for byte in img_dat:
        outfile.write(byte.to_bytes(1,byteorder='big'))
    outfile.close()

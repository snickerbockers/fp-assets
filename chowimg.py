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
from copy import copy

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
    len_expect = 0

    while bytes_read < hunk_len:
        print("%d bytes read, hunk length is %d" % (bytes_read, hunk_len))
        ctrl_byte = struct.unpack("B", infile.read(1))[0]
        bytes_read += 1

        literal_byte_count = ctrl_byte >> 4
        literal_byte_count, vll_len = load_vll(infile, ctrl_byte >> 4)
        bytes_read += vll_len

        literal_byte_start = len(hunk)
        literal_bytes = [ ] # TODO: DELETE THIS
        for index in range(literal_byte_count):
            bt = struct.unpack("B", infile.read(1))[0]
            literal_bytes.append(bt) # TODO: DELETE THIS
            hunk.append(bt)
            bytes_read += 1
        len_expect += literal_byte_count

        if bytes_read >= hunk_len:
            break

        # now for the sliding window
        rewind_distance = struct.unpack("<H", infile.read(2))[0]
        window_start = len(hunk) - rewind_distance

        if window_start < 0:
            print("ERROR: file attempt to replay starting %d bytes before end of hunk, but hunk is only %d bytes!" % (rewind_distance, len(hunk)), file = sys.stderr)
            exit(1)

        bytes_read += 2
        window_byte_count, vll_len = load_vll(infile, ctrl_byte & 0xf)
        window_byte_count += 4
        bytes_read += vll_len

        len_expect += window_byte_count

        if window_start >= len(hunk):
            print("ERROR: file references %d byte replay starting from index of %d but hunk only contains %d bytes!" % (window_byte_count, index, len(hunk)), file = sys.stderr)
            exit(1)

        for index in range(window_byte_count):
#           print("window_start is %d, index is %d" % (window_start, index))
            hunk.append(hunk[window_start + index])
 #           except IndexError as error:
#                print("ERROR: attempt to 

        if verbose:
            print("\t\t%u literal bytes, %u repeat bytes starting %u from the end" % (literal_byte_count, window_byte_count, rewind_distance))
            for bt in literal_bytes:
                print("\t\t\t%02x" % bt)
#            for index in range(literal_byte_count):
#                print("\t\t\t%02x" % hunk[index + literal_byte_start])

    print("expected length %d" % len_expect)
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

class subhunk:
    def __init__(self):
        self.literal = [ ]
        self.rewind = 0
        self.replay_len = 0

class compressor:
    def __init__(self, verbose = False):
        self.window = bytearray()
        self.state = "LITERAL"
        self.cur_match = bytearray()
        self.cur_match_start = -1
        self.window_end = 0
        self.literal = bytearray()
        self.uncompressed_len = 0
        self.verbose = verbose

        self.hunks = []
        self.sub = []

    @staticmethod
    def encode_vll(val):
        """
        return a list of values <= 255 which can be added together
        to get *val*.  The first value will be no greater than 15,
        and the last value will be less than 255
        """
        bts = bytearray()
        if val < 0:
            print("ERROR: attempt to encode negative value %d as VLL" % val, file=sys.stderr)
            exit(1)
        if val < 15:
            bts.append(val)
            return bts
        bts.append(15)
        val -= 15
        while val >= 255:
            bts.append(255)
            val -= 255
        bts.append(val)
        return bts

    def push_byte(self, cur_byte):
        self.uncompressed_len += 1
        if len(self.window) >= 65536:
            if len(self.cur_match) < 4:
                self.sub.append(subhunk())
                self.sub[-1].literal = bytearray(self.cur_match)
            else:
                self.sub.append(subhunk())
                self.sub[-1].literal = self.literal
                self.sub[-1].rewind = self.window_end - self.cur_match_start
                self.sub[-1].replay_len = len(self.cur_match)
                if self.sub[-1].replay_len < 4:
                    print("WHAT THE FUCK replay_len IS %d" % 4,file = sys.stderr)

            print("SPLIT OFF NEW HUNK, OLD HUNK LENGTH IS %d" % len(self.window))
            self.hunks.append((len(self.window), self.sub))
            self.window = bytearray()
            self.state = "LITERAL"
            self.cur_match = bytearray()
            self.cur_match_start = -1
            self.window_end = 0
            self.literal = bytearray()
            self.uncompressed_len = 0
            self.sub = []

        while True:
            if self.state == "REWIND":
                next_match = copy(self.cur_match)
                next_match.append(cur_byte)

                subseq_start = self.window.rfind(next_match)
                if subseq_start >= 0:
                    # add cur_byte to self.cur_match and self.window
                    self.cur_match = next_match
                    self.cur_match_start = subseq_start
                    self.window.append(cur_byte)
                    return
                else:
                    if len(self.cur_match) < 4:
                        # the compression format used by chowdren does not
                        # allow for replays of less than four bytes, so add this
                        # to the literal instead.
                        self.literal += self.cur_match
                        self.cur_match = bytearray()
                        self.state = "LITERAL"
                        continue

                    self.sub.append(subhunk())

                    # save offset to replay data (from end of window)
                    # TODO: make sure it doesn't overflow a 16-bit int here
                    #print("self.window_end is %d, self.cur_match_start is %d" % (self.window_end,self.cur_match_start))
                    self.sub[-1].literal = self.literal
                    self.sub[-1].rewind = self.window_end - self.cur_match_start
                    self.sub[-1].replay_len = len(self.cur_match)
                    if self.sub[-1].replay_len < 4:
                        print("WHAT THE FUCK replay_len IS %d" % 4,file = sys.stderr)

                    if self.verbose:
                        if len(self.cur_match):
                            print("%d literal bytes, %d repeat bytes starting %d from the end (index %d)" % \
                                  (len(self.literal), len(self.cur_match), self.window_end - self.cur_match_start, self.cur_match_start))
                        else:
                            print("%d literal bytes, %d repeat bytes starting XXX from the end" % (len(self.literal), len(self.cur_match)))

                    # reset state machine
                    self.state = "LITERAL"
                    self.literal = bytearray()
                    self.cur_match = bytearray()
            else:
                if cur_byte in self.window:
                    self.state = "REWIND"
                    self.window_end = len(self.window) # + len(self.literal)
                else:
                    self.literal.append(cur_byte)
                    self.window.append(cur_byte)
                    return

    def get_raw_data(self):
        if len(self.literal) or len(self.cur_match):
            if self.verbose:
                print("adding residual data to the end of the final hunk")
            # need to add residual unsaved data to end of hunk
            if len(self.cur_match) and len(self.cur_match) < 4:
                self.sub.append(subhunk())
                self.sub[-1].literal = self.cur_match
            else:
                self.sub.append(subhunk())
                self.sub[-1].literal = self.literal
                self.sub[-1].rewind = self.window_end - self.cur_match_start
                self.sub[-1].replay_len = len(self.cur_match)
                if self.sub[-1].replay_len < 4:
                    print("WHAT THE FUCK replay_len IS %d" % 4,file = sys.stderr)
            self.literal = bytearray()
            self.cur_match = bytearray()

        if len(self.sub):
            # need to complete residual hunk
            self.hunks.append((len(self.window), self.sub))
            self.window = bytearray()
            self.sub = []

        data = bytes()
        # compile the hunks into raw binary data
        for hk in self.hunks:
            hunkdat = bytes()
            for sh in hk[1]:
                no_replay = False
                if sh.replay_len < 4:
                    # TODO: maybe check to make sure this only happens when the entire hunk is
                    #       a single subhunk's literal section
                    # print("ERROR: replay_len is %d" % sh.replay_len, file=sys.stderr)
                    # print("original uncompressed length was %d bytes" % self.uncompressed_len, file=sys.stderr)
                    # exit(1)
                    sh.replay_len = 4# replay length will be ignored if the literal section contains the entire hunk
                    no_replay = True

                litlen = compressor.encode_vll(len(sh.literal))
                replen = compressor.encode_vll(sh.replay_len - 4)
                control_byte = (litlen[0] << 4) | replen[0]

                hunkdat += struct.pack("B", control_byte) + litlen[1:] + sh.literal

                if not no_replay:
                    hunkdat += struct.pack("<H", sh.rewind) + replen[1:]
            hunklen = len(hunkdat)
            data += struct.pack("<I", hunklen) + hunkdat

        compressed_len = len(data)
        print("original uncompressed length was %d bytes" % self.uncompressed_len)
        print("compressed length is %d bytes" % compressed_len)
        print("compression ratio is %f%%" % (100 * compressed_len / self.uncompressed_len))
        return data

    def save(self, stream):
        # write data to file
        stream.write(self.get_raw_data())

def compress_img(rawdat, verbose=False):
    print("****** BEGIN NEW IMAGE COMPRESSION ******")
    comp = compressor(verbose=verbose)
    for bt in rawdat:
        comp.push_byte(bt)
    return comp.get_raw_data()

if __name__=='__main__':
    usage_string="""\
    Usage: %s [-v] [-w width -h height] <in-file> <out-file>

    -v    Verbose-mode
    -h    set height of image (mandatory when using -x)
    -w    set width of image (mandatory when using -x)
    -w    set width

    chowimg.py converts images between two different image formats.
    It should not be run as an independent program unless you're doing testing.
    It primarily exists as a support module for fp-assets.py, which is probably
    what you actually want to run.

    the conversion done is based on the file extensions of in-file and
    out-file.  If they do not match the below extensions then this will not
    work.

    .png - Portable Network Graphics file
    .bin - chowdren-format compressed image
    .raw - uncompressed RGBA quads, 32-bits per pixel

    when the destination-type is .png, the width and height of the image must
    be supplied with the -w and -h options.  As an exception, the width and height
    will be determined automatically if the source-file is .png, but then you're converting
    from a .png img to a .png image and that's just stupid.
    """ % sys.argv[0]

    width = -1
    height = -1
    verbose = False

    # TODO: we don't actually need -r, -c and -x
    # we can just decide what to do based on file extensions
    try:
        opt_val, params = getopt(sys.argv[1:], "w:h:v")
        for option, value in opt_val:
            if option == "-w":
                width = int(value)
            elif option == "-h":
                height = int(value)
            elif option == "-v":
                print("verbose mode enabled", file=sys.stderr)
                verbose = True
    except GetoptError:
        print(usage_string)
        exit(1)

    src_file = params[0]
    dst_file = params[1]
    print("request to convert from %s to %s" % (src_file, dst_file))
    src_ext = src_file.rpartition('.')[2].casefold()
    dst_ext = dst_file.rpartition('.')[2].casefold()
    print("source extension is %s" % src_ext)

    if src_ext == 'png':
        img_obj = Image.open(src_file)
        if width < 0:
            width = img_obj.width
        if height < 0:
            height = img_obj.height
        img_dat = img_obj.tobytes()
    elif src_ext == 'bin':
        with open(src_file, "rb") as infile:
            infile.seek(0, 2)
            compressed_len = infile.tell()
            infile.seek(0)
            img_dat = load_img(infile, compressed_len, verbose)
    elif src_ext == 'raw':
        with open(src_file, "rb") as infile:
            img_dat = infile.read()
    else:
        print("ERROR: unrecognized source file extension \"%s\"" % src_ext, file=sys.stderr)
        exit(1)

    if dst_ext == 'png':
        if width < 0 or height < 0:
            print("ERROR: destination file type \"png\" required width (-w option) and height (-h option)", file=sys.stderr)
            exit(1)
        img_obj = Image.frombytes("RGBA", (width, height), bytes(img_dat))
        img_obj.save(dst_file)
    elif dst_ext == 'bin':
        with open(dst_file, "wb") as outfile:
            outfile.write(compress_img(img_dat, verbose=verbose))
    elif dst_ext == 'raw':
        with open(dst_file, "wb") as outfile:
            outfile.write(bytes(img_dat))
    else:
        print("ERROR: unrecognized destination file extension \"%s\"" % src_ext, file=sys.stderr)
        exit(1)

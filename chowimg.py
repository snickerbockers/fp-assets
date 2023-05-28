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
from array import array

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
    print("hunk length is %d" % hunk_len)

    bytes_read = 0
    len_expect = 0

    while bytes_read < hunk_len:
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
        self.lit = [ ]
        self.rewind = 0
        self.replay_len = 0

class compressor:
    def __init__(self, verbose = False):
        self.window = array('B')
        self.state = "LITERAL"
        self.cur_match = array('B')
        self.cur_match_start = -1
        self.window_end = 0
        self.literal = array('B')
        self.uncompressed_len = 0
        self.verbose = verbose

        # list of subhunk structures
        self.sub = [ ]

    @staticmethod
    def subseq(query, base):
        """
        subseq - search for subsequences

        returns the index of the beginning of the ~~first~~ last instance of query in base
        query and base should both be lists
        returns -1 if query does not appear within base
        """
        match = -1
        if len(query) > len(base):
            return -1

        start = 0
        stop = len(base) - len(query) + 1

        while start < stop:
            try:
                idx = base.index(query[0], start, stop)
                if query == base[idx:idx+len(query)]:
                    match = idx
                start = idx + 1
            except ValueError:
                break
        return match

    @staticmethod
    def encode_vll(val):
        """
        return a list of values <= 255 which can be added together
        to get *val*.  The first value will be no greater than 15,
        and the last value will be less than 255
        """
        if val < 0:
            print("ERROR: attempt to encode negative value %d as VLL" % val, file=sys.stderr)
            exit(1)
        if val < 15:
            return [ val ]
        seq = [ 15 ]
        val -= 15
        while val >= 255:
            seq.append(255)
            val -= 255
        seq.append(val)
        return seq

    def push_byte(self, cur_byte):
        while True:
            if self.state == "REWIND":
                next_match = copy(self.cur_match)
                next_match.append(cur_byte)

                subseq_start = compressor.subseq(next_match, self.window)
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
                        self.cur_match = array('B')
                        self.state = "LITERAL"
                        continue

                    self.sub.append(subhunk())

                    # save offset to replay data (from end of window)
                    # TODO: make sure it doesn't overflow a 16-bit int here
                    #print("self.window_end is %d, self.cur_match_start is %d" % (self.window_end,self.cur_match_start))
                    self.sub[-1].literal = self.literal
                    self.sub[-1].rewind = self.window_end - self.cur_match_start
                    self.sub[-1].replay_len = len(self.cur_match)

                    if self.verbose:
                        if len(self.cur_match):
                            print("%d literal bytes, %d repeat bytes starting %d from the end (index %d)" % \
                                  (len(self.literal), len(self.cur_match), self.window_end - self.cur_match_start, self.cur_match_start))
                        else:
                            print("%d literal bytes, %d repeat bytes starting XXX from the end" % (len(self.literal), len(self.cur_match)))

                    self.uncompressed_len += len(self.literal) + len(self.cur_match)
                    if self.uncompressed_len != len(self.window):
                        print("WARNING: self.uncompressed_len is %d but len(self.window) is %d" % (self.uncompressed_len, len(self.window)), file=sys.stderr)
                    # reset state machine
                    self.state = "LITERAL"
                    self.literal = array('B')
                    self.cur_match = array('B')
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
            # need to add residual unsaved data to end of hunk
            if len(self.cur_match) < 4:
                self.sub[-1].literal += self.literal + self.cur_match
            else:
                self.sub.append(subhunk())
                self.sub[-1].literal = self.literal
                self.sub[-1].rewind = self.window_end - self.cur_match_start
                self.sub[-1].replay_len = len(self.cur_match)
                print("final subhunk added: %d literal bytes, %d rewind, %d replay bytes" % (len(self.sub[-1].literal), self.sub[-1].rewind, self.sub[-1].replay_len))
            self.literal = array('B')
            self.cur_match = array('B')

        # compile the subhunks into raw binary data
        data = bytes()
        for sh in self.sub:
            if sh.replay_len < 4:
                print("ERROR: replay_len is %d" % sh.replay_len)
                exit(1)

            litlen = compressor.encode_vll(len(sh.literal))
            replen = compressor.encode_vll(sh.replay_len - 4)
            control_byte = (litlen[0] << 4) | replen[0]

            data += struct.pack("B", control_byte)
            for bt in litlen[1:]:
                data += struct.pack("B", bt)

            for bt in sh.literal:
                data += struct.pack("B", bt)

            data += struct.pack("<H", sh.rewind)
            for bt in replen[1:]:
                data += struct.pack("B", bt)

        compressed_len = len(data) + 4
        print("original uncompressed length was %d bytes" % self.uncompressed_len)
        print("compressed length is %d bytes" % compressed_len)
        print("compression ratio is %f%%" % (100 * compressed_len / self.uncompressed_len))
        print("there are %d bytes in the window" % len(self.window))
        # if self.uncompressed_len != len(self.window):
        #     print("WARNING: uncompressed length should be %d but instead it's %d!" % (len(self.window), self.uncompressed_len), file = sys.stderr)
        datlen = len(data)
        print("hunk length is %d" % datlen)

        data = struct.pack("<I", datlen) + data
        return data

    def save(self, stream):
        # write data to file
        stream.write(self.get_raw_data())

def compress_img(rawdat, verbose=False):
    comp = compressor(verbose=verbose)
    for bt in rawdat:
        comp.push_byte(bt)
    return comp.get_raw_data()

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
                print("verbose mode enabled", file=sys.stderr)
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

        with open(params[0], "rb") as infile:
            infile.seek(0, 2)
            compressed_len = infile.tell()
            infile.seek(0)
            img_dat = load_img(infile, compressed_len, verbose)

        expected_len = width * height * 4
        print("total uncompressed image length is %u bytes" % len(img_dat))
        if expected_len != len(img_dat):
            print("WARNING: image data length %d does not match expected length of %d" % \
                  (len(img_dat), expected_len), file=sys.stderr)

        img_obj = Image.frombytes("RGBA", (width, height), bytes(img_dat))
        img_obj.save(params[1])
    elif mode == 2:
        with open(params[1], "wb") as outf:
            outf.write(compress_img(Image.open(params[0]).tobytes(), verbose=verbose))
    else:
        # should be impossible to get here anyways
        print(usage_string)
        exit(1)

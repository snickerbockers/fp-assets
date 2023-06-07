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

# consistency test for fp-assets.py
# first extract a given Assets.dat with fp-assets.py
# then, recompress it with fp-assets.py
# then extract the file that was just recompressed with fp-assets.py
# there are now two separate .png files for each image.  If there are no bugs
#     in chowimg then the two .png files should match byte-for-byte

import sys
import os
import hashlib

def md5sum(path):
    hasher = hashlib.md5()
    stream = open(path, "rb")
    buf = stream.read(4096)
    while buf:
        hasher.update(buf)
        buf = stream.read(4096)
    stream.close()
    return hasher.hexdigest()

TEST_DIR="consistency_test"

src_dat=sys.argv[1]

os.system("[ -d %s ] && rm -r %s" % (TEST_DIR, TEST_DIR))
os.mkdir(TEST_DIR)

first_extract_path=os.path.join(TEST_DIR, "first_extract")
second_extract_path=os.path.join(TEST_DIR, "second_extract")
recompress_path=os.path.join(TEST_DIR, "recompressed_assets.dat")

# extract it
os.system("./fp-assets.py -xf %s %s" % (src_dat, first_extract_path))

# recompress it
os.system("./fp-assets.py -cf %s %s" % (recompress_path, first_extract_path))

# extract the new assets.dat file we just created
os.system("./fp-assets.py -v -m %s -xf %s %s" % (os.path.join(first_extract_path, "format.json"), recompress_path, second_extract_path))

retcode=0
for path in os.listdir(os.path.join(first_extract_path, "images")):
    ext = path.rpartition('.')[2].casefold()
    if ext != 'png':
        continue
    path1 = os.path.join(first_extract_path, "images", path)
    path2 = os.path.join(second_extract_path, "images", path)
    if md5sum(path1) != md5sum(path2):
        print("ERROR: md5sum of %s and %s do not match!" % (path1, path2))
        retcode+=1

if retcode == 0:
    print("all images have matching checksums")
exit(retcode)

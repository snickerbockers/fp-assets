# fp-assets
Extractor/archiver tool for Freedom Planet's Assets.dat file.

## Usage
fp-assets.py -c | -x [ -f|--file=<in-file> ] [pathname]

in-file is a path to your Assets.dat file.  it defaults to ./Assets.dat
pathname is the path to the directory to be extracted to/created from.
    It defaults to ./Assets/

-c creates a new Assets.dat.
-x extracts Assets.dat

extracting will exit with an error if pathname already exists.

## Output
The out-dir will contain a hierarchy of all files in Assets.dat this script
could find.

Do not rename these files because that will confuse it when it tries to create a
new Assets.dat from this data.

The audio/ and images/ subdirectories contain several text files ending in
"_meta.txt".  These contain metadata of unknown purpose.  It might be some sort
of key used by Chowdren to identify individual assets or it might be something
else entirely.

## Prerequisites
* Python 2.7
* PIL (Python Imaging Library)
* zlib

## Contributing
Don't use tabs or let columns get longer than 80 characters

## Legal
This software is public domain, see LICENSE for details.

-- snickerbockers was here, 2016
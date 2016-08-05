# fp-assets
Extractor (and eventually archiver) tool for Freedom Planet's Assets.dat file.

## Usage
fp-assets.y [ -f|--in-file=<in-file> ] [ -d|--out-dir=<out-dir> ]

in_file is a path to your Assets.dat file.  it defaults to ./Assets.dat
out_dir is a path to where you want the Assets to go.  It defaults to ./Assets/

This script will exit with an error if out-dir already exists.

## Output
The out-dir will contain a hierarchy of all files in Assets.dat this script could find.
Do not rename these files because that will confuse it when it tries to create a new Assets.dat from this data.
The audio/ and images/ subdirectories contain several text files ending in "_meta.txt".  These contain metadata of unknown purpose.  It might be some sort of key used by Chowdren to identify individual assets or it might be something else entirely.

## Prerequisites
* Python 2.7
* PIL (Python Imaging Library)
* zlib

## Missing features
* This program can't create a new Assets.dat yet
* This program can't extract fonts because I don't understand how those work yet
* I have absolutely no idea what goes before 0x83fa

## Contributing
Don't use tabs or let columns get longer than 80 characters

## Legal
This software is public domain, see LICENSE for details.

-- snickerbockers was here, 2016

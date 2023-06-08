# fp-assets
Extractor/archiver tool for Freedom Planet's Assets.dat file.  You can use this
to replace art, fonts, sounds, and shaders with whatever you want.

Assets.dat is an archive containing most of the game's art assets, including
sprites and sounds.  It is encoded with a proprietary format that is specific
to the chowdren engine (and to some extent specific to each version of each game,
see [how metadata works below](#how-metadata-works)).  I have reverse-engineered this
format myself.

## Usage
```
Usage: %s -c | -x [ -f|--file=<in-file> ] [-m metadata_file] [-r] [pathname]

in-file is a path to your Assets.dat file.  it defaults to ./Assets.dat
pathname is the path to the directory to be extracted to/created from.
    It defaults to ./Assets/

-c creates a new Assets.dat.
-x extracts Assets.dat
-m is the path to a json file describing Assets.dat metadata; this is only required if fp-assets.py cannot auto-identify your file
-r extracts images as raw "binary blobs" instead of decoding them and converting to PNG; only use this if you *absolutely* understand what you're doing.

extracting will exit with an error if pathname already exists.
```
## how metadata works

Assets.dat's metadata block consists of an array of offsets to different
files within the archive.  Frustratingly, **the offset to this metadata block
and the number of each type of asset is hard-coded into the game!**  Even worse,
there are also two different methods that different verisons of this game will use
to compress images: either zlib (in older versions) or a newer proprietary compression
scheme i had to reverse engineer myself (see chowimg.py for the implementation, it's
just a simple moving-window algorithm but there are a few frustrating special cases to
consider).  Naturally, Assets.dat doesn't have any metadata to specify which compression
scheme is being used.

Because of this, fp-assets.py needs to have special support for each different version.
We accomplish this by creating a file called format.json which contains all the
metadata that is hard-coded into the game.

fp-assets.py can automatically identify supported versions of Assets.dat based
on the md5 checksum of Assets.dat, but if you're extracting an Assets.dat which is
not recognized (eg, one which has been modified with fp-assets.py) then you're going
to need to supply format.json yourself with the -m option.

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
* Python 3 (i tested with 3.11.3, not sure how far back this thing will work)
* PIL (Python Imaging Library)
* zlib

## Contributing
Don't use tabs or let columns get longer than 80 characters

## Legal
This software is public domain, see LICENSE for details.

-- snickerbockers was here, 2016, 2023
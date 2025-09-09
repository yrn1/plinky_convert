# Converter for Plinky samples

This is a set of Python scripts to convert samples to and from Plinky UF2 format. Comes without warranty, use at your own risk!

## UF2 to WAV

Converts UF2 files from Plinky to 32kHz, 16bit mono WAV files.

    ./uf22wav.py <uf2_files>

This creates `.wav` files with the same basename as the input `.uf2` files.

**Warning**: this will overwrite existing files without asking!

## WAV to UF2

Converts a 32kHz, 16bit mono WAV file to a Plinky `SAMPLEX.UF2` file.

You must specify a `<sample_number>` between 0 to 7. The number is embedded in the file. You should also not rename the generated file when copying it to Plinky.

    ./wav2uf2.py <wav_file> <sample_number>

**Warning**: this will overwrite existing files without asking!

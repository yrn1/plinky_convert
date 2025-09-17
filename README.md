# Convert WAV to Plinky sample

> Warning: this is alpha-quality software without any guarantees.

## WAV to Plinky

[`wav2uf2.py`](wav2uf2.py) converts a 32kHz, 16bit, mono WAV file with cue
markers to a plinky `SAMPLE<index>.UF2` and updates a `PRESETS.UF2` file to
include the correct waveform, sample length and split points.

### Procedure

* Mount your Plinky on your computer and copy `PRESETS.UF2` to a local
  directory.
* While in that directory, execute the following command in a terminal:

        python wav2uf2.py <wav-file> <index>

  * `<wav-file>` is your 32kHz, 16bit, mono WAV file
  * `<index>` is the number that the sample will have on Plinky - 1.
     Yeah, we're computer nerds, so stuff starts at 0.

* This will create a `SAMPLE<index>.UF2` file.
* It will also update the `PRESETS.UF2` file in the current directory:
  * The waveform of the sample is updated.
  * The length of the sample is update.
  * The first 8 cue markers in the WAV file are converted to split points
    in `PRESET.UF2`. If there are less than 8 cue markers, then the remaining
    split points are evenly distributed in the remaining space.
* Copy `PRESETS.UF2` and `SAMPLE<index>.UF2` back to your Plinky.

## Plinky to WAV

[`uf22wav.py`](uf22wav.py) converts a `SAMPLE<index>.UF2` from Plinky to a
16bit, 32kHz, mono WAV file. Note that it does not set the sample length
correctly and it does not retrieve the split points.
#!/usr/bin/env python3
import sys
import struct
import wave
import math
import shutil
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')

UF2_MAGIC_START_0 = 0x0a324655
UF2_MAGIC_START_1 = 0x9e5d5157
UF2_MAGIC_END =     0x0ab16f30
UF2_FLAGS = 0x0
UF2_PAYLOAD_SIZE = 0x100
UF2_PAYLOAD_OFFSET = 32
UF2_FAMILY_ID = 0x0
UF2_BLOCK_SIZE = 512

SAMPLE_TARGET_ADDRESS_OFFSET = 0x40000000
SAMPLE_NUM_BLOCKS = 0x4000
SAMPLE_COUNT = 0x200000
SAMPLE_PADDING = b'\xff\xff'
SAMPLE_WAVEFORM_BLOCKSIZE = 1024

PRESET_TARGET_ADDRESS_OFFSET = 0x08080000
PRESET_PAGE_SIZE = 2048
PRESET_PAGE_FOOTER_SIZE = 8
PRESET_SYSPARAMS_SIZE = 16
PRESET_NUM_PRESETS = 32
PRESET_NUM_PATTERNS = 24
PRESET_NUM_SAMPLES = 8
PRESET_VERSION = 2

PRESET_PATTERNS_IDX = PRESET_NUM_PRESETS
PRESET_SAMPLES_IDX = PRESET_PATTERNS_IDX + 4 * PRESET_NUM_PATTERNS

#
# WAV file related methods
#
def read_wav(filename):
    with wave.open(filename, 'rb') as f:
        if f.getnchannels() != 1:
            raise ValueError('Only mono wav files are supported')
        if f.getsampwidth() != 2:
            raise ValueError('Only 16bit wav files are supported')
        if f.getframerate() != 32000:
            raise ValueError('Only 32kHz wav files are supported')
        if f.getnframes() > SAMPLE_COUNT:
            raise ValueError(f"Maximum {SAMPLE_COUNT} samples allowed")
        if f.getcomptype() != 'NONE':
            raise ValueError('Only uncompressed wav files are supported')
        bytes = f.readframes(SAMPLE_COUNT)
        pad_length = SAMPLE_COUNT - f.getnframes()
        bytes += SAMPLE_PADDING * pad_length
        return (bytes, f.getnframes())

# from scipy wave
def _skip_unknown_chunk(fid):
    data = fid.read(4)
    size = struct.unpack('<i', data)[0]
    if bool(size & 1):
      size += 1 
    fid.seek(size, 1)

# from scipy wave
def _read_riff_chunk(fid):
    str1 = fid.read(4)
    if str1 != b'RIFF':
        raise ValueError("Not a WAV file.")
    fsize = struct.unpack('<I', fid.read(4))[0] + 8
    str2 = fid.read(4)
    if (str2 != b'WAVE'):
        raise ValueError("Not a WAV file.")
    return fsize

# https://stackoverflow.com/questions/20011239/read-markers-of-wav-file#20396562
def read_wav_markers(filename):
    with open(filename, 'rb') as f:
        fsize = _read_riff_chunk(f)
        cues = []
        while (f.tell() < fsize):
            chunk_id = f.read(4)
            if chunk_id == b'cue ':
                size, numcue = struct.unpack('<ii',f.read(8))
                for c in range(numcue):
                    id, position, datachunkid, chunkstart, blockstart, sampleoffset = struct.unpack('<iiiiii',f.read(24))
                    cues.append(position)
            else:
                _skip_unknown_chunk(f)
        return cues

def create_splits(cues, length):
    splits = []
    splits.extend(sorted(cues[:8]))
    if (len(splits) == 0):
        splits.append(0)
    missing = 8 - len(splits)
    last_split = splits[-1]
    split_size = (length - last_split) / (missing + 1)
    for i in range(1, missing + 1):
        splits.append(int(last_split + i * split_size))
    return splits

def create_waveform(data):
    blocks = [data[i:i + SAMPLE_WAVEFORM_BLOCKSIZE * 2] for i in range(0, len(data), SAMPLE_WAVEFORM_BLOCKSIZE * 2)]
    waveform = []
    for block in blocks:
        peak = 0
        for s in range(0, len(block), 2):
            sample = struct.unpack_from('<h', block, s)
            peak = max(peak, abs(sample[0]))
        waveform.append(math.floor(peak / 1024))
    packed = bytearray(1024)
    for i in range(0, len(waveform), 2):
        sample0 = max(min(waveform[i], 15), 0)
        sample1 = max(min(waveform[i + 1], 15), 0)
        struct.pack_into('<B', packed, int(i / 2), sample0 + 16 * sample1)
    return packed

#
# UF2 file related methods
#
def read_uf2(filename):
    with open(filename, 'rb') as f:
        content = f.read()

    blocks = [content[i:i+UF2_BLOCK_SIZE] for i in range(0, len(content), UF2_BLOCK_SIZE)]
    data_blocks = []
    previous_address = None
    for block in blocks:
        magic_start_0, magic_start_1, flags, target_address, payload_size, block_no, num_blocks, family_id = struct.unpack_from('<IIIIIIII', block, 0)
        logging.debug(f"UF2 magic0={magic_start_0:#0x} magic1={magic_start_1:#0x} flags={flags:#0x} target={target_address:#0x} size={payload_size:#0x} block={block_no:#0x} blocks={num_blocks:#0x} family={family_id:#0x}")

        if previous_address is not None and target_address != previous_address + payload_size:
            raise ValueError("UF2 data is not contiguous.")
        previous_address = target_address
        
        data_blocks.append(block[UF2_PAYLOAD_OFFSET:UF2_PAYLOAD_OFFSET + payload_size])
    
    return b''.join(data_blocks)

def create_backup(filename):
    if os.path.exists(filename):
        suf = datetime.now().strftime("-%Y%m%d%H%M%S")
        i = 1
        while os.path.exists(filename + suf + "-" + str(i)):
            i += 1
        shutil.copy(filename, filename + suf + "-" + str(i))

def write_uf2(data, filename, target_address):
    create_backup(filename)
    with open(filename, 'wb') as f:
        blocks = [data[i:i+UF2_PAYLOAD_SIZE] for i in range(0, len(data), UF2_PAYLOAD_SIZE)]
        for i in range(0, len(blocks)):
            block_target_address = target_address + i * UF2_PAYLOAD_SIZE
            f.write(struct.pack('<IIIIIIII', UF2_MAGIC_START_0, UF2_MAGIC_START_1, UF2_FLAGS, block_target_address, UF2_PAYLOAD_SIZE, i, len(blocks), UF2_FAMILY_ID))
            f.write(data[i * UF2_PAYLOAD_SIZE:i * UF2_PAYLOAD_SIZE + UF2_PAYLOAD_SIZE])
            f.write(b'\x00' * (UF2_BLOCK_SIZE - UF2_PAYLOAD_SIZE - UF2_PAYLOAD_OFFSET - 4))
            f.write(struct.pack('<I', UF2_MAGIC_END))
    logging.info(f"Wrote {filename}")

def write_uf2sample(data, index):
    filename = f"SAMPLE{index}.UF2"
    write_uf2(data, filename, SAMPLE_TARGET_ADDRESS_OFFSET + index * SAMPLE_NUM_BLOCKS * UF2_PAYLOAD_SIZE)

#
# PRESETS related methods
#
def read_page_footer(data, offset):
    idx, version, crc, seq = struct.unpack_from('<BBHI', data, offset + PRESET_PAGE_SIZE - PRESET_PAGE_FOOTER_SIZE)
    return (idx, version, crc, seq)

def find_sample_offset(data, index):
    preset_idx = PRESET_SAMPLES_IDX + index
    cur_seq = 0
    offset = 0

    for o in range(0, len(data), PRESET_PAGE_SIZE):
        idx, version, crc, seq = read_page_footer(data, o)
        if idx == preset_idx and version == PRESET_VERSION:
            if seq > cur_seq:
                cur_seq = seq
                offset = o
    return offset

def calculate_page_crc(data, offset):
    hash = 123
    for i in range(offset, offset + PRESET_PAGE_SIZE - PRESET_PAGE_FOOTER_SIZE):
        hash = (hash * 23 + data[i]) % 0x10000
    return hash

def read_sample_info(data, offset):
    waveform, split0, split1, split2, split3, split4, split5, split6, split7, sample_len, note0, note1, note2, note3, note4, note5, note6, note7, pitched, loop = struct.unpack_from('<1024s8ii8bBB', data, offset)
    splits = [split0, split1, split2, split3, split4, split5, split6, split7]
    notes = [note0, note1, note2, note3, note4, note5, note6, note7]
    return (waveform, sample_len, splits, notes, pitched, loop)

def print_sample_page(msg, data, index):
    offset = find_sample_offset(data, index)
    idx, version, crc, seq = read_page_footer(data, offset)
    ccrc = calculate_page_crc(data, offset)
    logging.debug("")
    logging.debug(msg)
    logging.debug(f"Presets Sample data length={len(data)}")
    logging.debug(f"Presets Sample footer idx={idx} version={version} crc={crc:#0x} calculated_crc={ccrc:#0x} seq={seq}")
    waveform, sample_len, splits, notes, pitched, loop = read_sample_info(data, offset)
    logging.debug(f"Presets Sample length={sample_len}, pitched={pitched}, loop={loop}")
    logging.debug(f"Presets Sample splits={[f"{x:02x}" for x in splits]}")
    logging.debug(f"Presets Sample notes={notes}")
    logging.debug(f"Presets Sample waveform={''.join([f"{x:02x}" for x in waveform])}")

def update_sample_page(data, index, sample_len, waveform, splits):
    ba = bytearray(data)
    offset = find_sample_offset(data, index)
    struct.pack_into('<1024s8ii', ba, offset, waveform, splits[0], splits[1], splits[2], splits[3], splits[4], splits[5], splits[6], splits[7], sample_len)
    crc = calculate_page_crc(ba, offset)
    struct.pack_into('<H', ba, offset + PRESET_PAGE_SIZE - PRESET_PAGE_FOOTER_SIZE + 2, crc)
    return ba

def main(filename, index):
    if not os.path.exists("PRESETS.UF2"):
        logging.info("This script must be run in a directory that contains PRESETS.UF2.")
        logging.info("It will be updated to contain the waveform, length and split points.")
        logging.info("Please don't run it in the mounted PLINKY volume.")
        sys.exit(1)

    logging.info(f"Processing {filename}")
    sample_data, sample_len = read_wav(filename)
    logging.debug(f"Sample length {sample_len}")
    write_uf2sample(sample_data, index)

    waveform = create_waveform(sample_data)
    markers = read_wav_markers(filename)
    logging.debug(f"Markers from WAV {markers}")

    splits = create_splits(markers, sample_len)
    logging.debug(f"Completed splits {splits}")

    presets_data = read_uf2("PRESETS.UF2")
    print_sample_page("Before update:", presets_data, index)
    updated_presets_data = update_sample_page(presets_data, index, sample_len, waveform, splits)
    write_uf2(updated_presets_data, "PRESETS.UF2", PRESET_TARGET_ADDRESS_OFFSET)

    presets_data = read_uf2("PRESETS.UF2")
    print_sample_page("After update:", presets_data, index)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        logging.info(f"Usage: python {sys.argv[0]} <file.wav> <index>")
        logging.info("  <file.wav> must be a 32kHz, 16bit mono WAV file.")
        logging.info("     The first 8 RIFF CUE points will be converted to split points.")
        logging.info("  <index> is the index where the sample will live in Plinky. 0 to 7.")
        sys.exit(1)
    
    filename = sys.argv[1]
    index = int(sys.argv[2])
    main(filename, index)

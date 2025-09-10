#!/usr/bin/env python3
import sys
import os
import struct
import wave
import math

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

PRESET_PAGE_SIZE = 2048
PRESET_PAGE_FOOTER_SIZE = 8
PRESET_SYSPARAMS_SIZE = 16
PRESET_NUM_PRESETS = 32
PRESET_NUM_PATTERNS = 24
PRESET_NUM_SAMPLES = 8

PRESET_PATTERNS_IDX = PRESET_NUM_PRESETS
PRESET_SAMPLES_IDX = PRESET_PATTERNS_IDX + 4 * PRESET_NUM_PATTERNS

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
    split_size = (SAMPLE_COUNT - last_split) / (missing + 1)
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
        waveform.append(round(peak / 1024))
    packed = bytearray(1024)
    for i in range(0, len(waveform), 2):
        sample0 = max(min(waveform[i], 15), 0)
        sample1 = max(min(waveform[i + 1], 15), 0)
        struct.pack_into('<B', packed, int(i / 2), sample0 + 16 * sample1)
    return packed

def read_uf2(filename):
    with open(filename, 'rb') as f:
        content = f.read()

    blocks = [content[i:i+UF2_BLOCK_SIZE] for i in range(0, len(content), UF2_BLOCK_SIZE)]
    data_blocks = []
    previous_address = None
    for block in blocks:
        (magic_start_0, magic_start_1, flags, target_address, payload_size, block_no, num_blocks, family_id) = struct.unpack_from('<IIIIIIII', block, 0)
        # print(f"U> magic0={magic_start_0:#0x} magic1={magic_start_1:#0x} flags={flags:#0x} target={target_address:#0x} size={payload_size:#0x} block={block_no:#0x} blocks={num_blocks:#0x} family={family_id:#0x}")

        if previous_address is not None and target_address != previous_address + payload_size:
            raise ValueError("UF2 data is not contiguous.")
        previous_address = target_address
        
        data_blocks.append(block[UF2_PAYLOAD_OFFSET:UF2_PAYLOAD_OFFSET + payload_size])
    
    return b''.join(data_blocks)

def write_uf2(data, filename, target_address):
    with open(filename, 'wb') as f:
        blocks = [data[i:i+UF2_PAYLOAD_SIZE] for i in range(0, len(data), UF2_PAYLOAD_SIZE)]
        i = 0
        for block in blocks:
            block_target_address = target_address + i * UF2_PAYLOAD_SIZE
            f.write(struct.pack('<IIIIIIII', UF2_MAGIC_START_0, UF2_MAGIC_START_1, UF2_FLAGS, block_target_address, UF2_PAYLOAD_SIZE, i, len(blocks), UF2_FAMILY_ID))
            f.write(data[i * UF2_PAYLOAD_SIZE:i * UF2_PAYLOAD_SIZE + UF2_PAYLOAD_SIZE])
            f.write(b'\x00' * (UF2_BLOCK_SIZE - UF2_PAYLOAD_SIZE - UF2_PAYLOAD_OFFSET - 4))
            f.write(struct.pack('<I', UF2_MAGIC_END))
            i += 1
    print(f"U> Wrote {filename}")

def write_uf2sample(data, index):
    filename = f"SAMPLE{index}.UF2"
    write_uf2(data, filename, SAMPLE_TARGET_ADDRESS_OFFSET + index * SAMPLE_NUM_BLOCKS * UF2_PAYLOAD_SIZE)

def read_page_footer(data, offset):
    # typedef struct PageFooter {
    # 	u8 idx; // preset 0-31, pattern (quarters!) 32-127, sample 128-136, blank=0xff
    # 	u8 version;
    # 	u16 crc;
    # 	u32 seq;
    # } PageFooter;
    tuple = struct.unpack_from('<BBHI', data, offset + PRESET_PAGE_SIZE - PRESET_PAGE_FOOTER_SIZE)
    (idx, version, crc, seq) = tuple
    return tuple

def calculate_page_crc(data, offset):
    hash = 123
    for i in range(offset, offset + PRESET_PAGE_SIZE - PRESET_PAGE_FOOTER_SIZE):
        hash = (hash * 23 + data[i]) % 0x10000
    return hash

def read_sample_info(data, offset):
    # typedef struct SampleInfo {
    # 	u8 waveform4_b[1024]; // 4 bits x 2048 points, every 1024 samples
    # 	int splitpoints[8];
    # 	int samplelen; // must be after splitpoints, so that splitpoints[8] is always the length.
    # 	s8 notes[8];
    # 	u8 pitched;
    # 	u8 loop; // bottom bit: loop; next bit: slice vs all
    # 	u8 paddy[2];
    # } SampleInfo;
    tuple = struct.unpack_from('<1024s8ii8bBB', data, offset)
    (waveform, split0, split1, split2, split3, split4, split5, split6, split7, sample_len, note0, note1, note2, note3, note4, note5, note6, note7, pitched, loop) = tuple
    return tuple

def find_sample_offset(data, index):
    # typedef struct FlashPage {
    # 	union {
    # 		u8 raw[FLASH_PAGE_SIZE - sizeof(SysParams) - sizeof(PageFooter)];
    # 		Preset preset;
    # 		PatternQuarter pattern_quarter;
    # 		SampleInfo sample_info;
    # 	};
    # 	SysParams sys_params;
    # 	PageFooter footer;
    # } FlashPage;
    preset_idx = PRESET_SAMPLES_IDX + index
    cur_seq = 0
    offset = 0

    for o in range(0, len(data), PRESET_PAGE_SIZE):
        (idx, version, crc, seq) = read_page_footer(data, o)
        if idx == preset_idx:
            if seq > cur_seq:
                cur_seq = seq
                offset = o
    return offset

def update_sample_page(data, index):
    offset = find_sample_offset(data, index)
    (idx, version, crc, seq) = read_page_footer(data, offset)
    ccrc = calculate_page_crc(data, offset)
    print(f"U> footer idx={idx} version={version} crc={crc:#0x} ({ccrc:#0x}) seq={seq}")
    (waveform, split0, split1, split2, split3, split4, split5, split6, split7, sample_len, note0, note1, note2, note3, note4, note5, note6, note7, pitched, loop) = read_sample_info(data, offset)

    print(f"U> sample splits=[{split0},{split1},{split2},{split3},{split4},{split5},{split6},{split7}], len={sample_len}")
    print(f"U> sample notes=[{note0},{note1},{note2},{note3},{note4},{note5},{note6},{note7}], pitched={pitched}, loop={loop}")
    # print(f"U> waveform={','.join([f"{x:02x}" for x in waveform])}")

def main(filename, index):
    print(f"S> Processing {filename}")
    (sample_data, sample_frames) = read_wav(filename)
    write_uf2sample(sample_data, index)

    print(f"S> sample frames {sample_frames}")
    waveform = create_waveform(sample_data)
    # print(f"S> waveform={','.join([f"{x:02x}" for x in waveform])}")
    markers = read_wav_markers(filename)
    print(f"S> markers {markers}")
    splits = create_splits(markers, sample_frames)

    presets_data = read_uf2("PRESETS-O.UF2")
    update_sample_page(presets_data, index)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <file.wav> <index>")
        sys.exit(1)
    
    filename = sys.argv[1]
    index = int(sys.argv[2])
    main(filename, index)

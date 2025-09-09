#!/usr/bin/env python3
import sys
import os
import struct
import wave

MAGIC_START_0 = 0x0a324655
MAGIC_START_1 = 0x9e5d5157
FLAGS = 0x0;
TARGET_ADDRESS_OFFSET = 0x40000000
PAYLOAD_SIZE = 0x100
NUM_BLOCKS = 0x4000
FAMILY_ID = 0x0
MAGIC_END =     0x0ab16f30
UF2_BLOCK_SIZE = 512
DATA_START_OFFSET = 32
SAMPLE_COUNT = 0x200000
SAMPLE_PADDING = b'\xff\xff'

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
        return bytes

def write_uf2(data, index):
    filename = f"SAMPLE{index}.UF2"
    with open(filename, 'wb') as f:
        for i in range(0, NUM_BLOCKS):
            target_address = TARGET_ADDRESS_OFFSET + index * NUM_BLOCKS * PAYLOAD_SIZE + i * PAYLOAD_SIZE
            f.write(struct.pack('<IIIIIIII', MAGIC_START_0, MAGIC_START_1, FLAGS, target_address, PAYLOAD_SIZE, i, NUM_BLOCKS, FAMILY_ID))
            f.write(data[i * PAYLOAD_SIZE:i * PAYLOAD_SIZE + PAYLOAD_SIZE])
            f.write(b'\x00' * (UF2_BLOCK_SIZE - PAYLOAD_SIZE - DATA_START_OFFSET - 4))
            f.write(struct.pack('<I', MAGIC_END))
    print(f"Wrote {filename}")

def main(filename, index):
    print(f"Processing {filename}")
    data = read_wav(filename)
    write_uf2(data, index)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <file.wav> <index>")
        sys.exit(1)
    
    filename = sys.argv[1]
    index = int(sys.argv[2])
    main(filename, index)

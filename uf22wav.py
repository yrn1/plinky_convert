#!/usr/bin/env python3
import sys
import os
import struct
import wave

UF2_BLOCK_SIZE = 512
UF2_PAYLOAD_OFFSET = 32

def read_uf2(filename):
    with open(filename, 'rb') as f:
        content = f.read()
    
    blocks = [content[i:i+UF2_BLOCK_SIZE] for i in range(0, len(content), UF2_BLOCK_SIZE)]
    data_blocks = []
    previous_address = None
    for block in blocks:
        (magic_start_0, magic_start_1, flags, target_address, payload_size, block_no, num_blocks, family_id) = struct.unpack_from('<IIIIIIII', block, 0)
        print(f"> magic0={magic_start_0:#0x} magic1={magic_start_1:#0x} flags={flags:#0x} target={target_address:#0x} size={payload_size:#0x} block={block_no:#0x} blocks={num_blocks:#0x} family={family_id:#0x}")

        if previous_address is not None and target_address != previous_address + payload_size:
            raise ValueError("UF2 data is not contiguous.")
        previous_address = target_address
        
        data_blocks.append(block[UF2_PAYLOAD_OFFSET:UF2_PAYLOAD_OFFSET + payload_size])
    
    return b''.join(data_blocks)

def write_wav(filename, data):
    wav_filename = filename.replace(".uf2", ".wav").replace(".UF2", ".wav")
    if wav_filename != filename:
        with wave.open(wav_filename, 'wb') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(32000)
            f.setcomptype('NONE', 'not compressed')
            f.writeframes(data)
    print(f"Wrote {wav_filename}")

def main(filenames):
    for filename in filenames:
        print(f"Processing {filename}")
        data = read_uf2(filename)
        write_wav(filename, data)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <file1.uf2> [<file2.uf2> ...]")
        sys.exit(1)
    
    filenames = sys.argv[1:]
    main(filenames)

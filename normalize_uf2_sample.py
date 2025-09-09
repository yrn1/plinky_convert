import sys
import os
import struct

UF2_BLOCK_SIZE = 512
DATA_START_OFFSET = 32
DATA_SIZE = 256
MAX_INT16 = 32767
MIN_INT16 = -32767

def read_uf2(filename):
    with open(filename, 'rb') as f:
        content = f.read()
    
    blocks = [content[i:i+UF2_BLOCK_SIZE] for i in range(0, len(content), UF2_BLOCK_SIZE)]
    
    # Extract data bytes from each block
    data_blocks = []
    previous_addr = None
    for block in blocks:
        addr = struct.unpack_from('<I', block, 12)[0]
        if previous_addr is not None and addr != previous_addr + DATA_SIZE:
            raise ValueError("UF2 data is not contiguous.")
        previous_addr = addr
        data_blocks.append(block[DATA_START_OFFSET:DATA_START_OFFSET + DATA_SIZE])
    
    return b''.join(data_blocks)

def write_raw_data(filename, data):
    raw_filename = filename.replace(".uf2", ".raw").replace(".UF2", ".raw")
    if raw_filename != filename:
        with open(raw_filename, 'wb') as f:
            f.write(data)

def normalize_audio(data):
    # Convert bytes to 16-bit signed integers
    audio_data = struct.unpack('<' + 'h' * (len(data) // 2), data)
    
    # Find the maximum absolute value in the audio data
    max_value = max(max(audio_data), abs(min(audio_data)))
    if max_value == 0:
        return data  # Nothing to normalize
    
    # Calculate normalization factor
    normalization_factor = MAX_INT16 / max_value
    
    # Normalize audio data
    normalized_data = [int(x * normalization_factor) for x in audio_data]
    
    # Pack back into bytes
    return struct.pack('<' + 'h' * len(normalized_data), *normalized_data)

def write_normalized_uf2(input_filename, normalized_data, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    with open(input_filename, 'rb') as f:
        content = f.read()
    
    blocks = [content[i:i+UF2_BLOCK_SIZE] for i in range(0, len(content), UF2_BLOCK_SIZE)]
    
    # Replace the data bytes in the UF2 blocks with normalized data
    normalized_blocks = []
    for i, block in enumerate(blocks):
        block_data = normalized_data[i * DATA_SIZE: (i + 1) * DATA_SIZE]
        new_block = block[:DATA_START_OFFSET] + block_data + block[DATA_START_OFFSET + DATA_SIZE:]
        normalized_blocks.append(new_block)
    
    output_filename = os.path.join(output_folder, os.path.basename(input_filename))
    with open(output_filename, 'wb') as f:
        f.write(b''.join(normalized_blocks))

def main(filenames):
    for filename in filenames:
        print(f"Processing {filename}...")
        data = read_uf2(filename)
        # write_raw_data(filename, data)
        write_raw_data(filename, data)
        normalized_data = normalize_audio(data)
        write_normalized_uf2(filename, normalized_data, 'normalized')
        print(f"Normalized UF2 file written to 'normalized' folder for {filename}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python normalize_uf2.py <file1.uf2> [<file2.uf2> ...]")
        sys.exit(1)
    
    filenames = sys.argv[1:]
    main(filenames)

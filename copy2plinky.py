import shutil
dst='/Volumes/PLINKY'
# print('copying presets')
# shutil.copy('PRESETS.UF2', dst)
for i in range(1,8):
    print('copying samples',i+1,'/8')
    shutil.copy(f'SAMPLE{i}.UF2', dst)
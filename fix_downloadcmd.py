#! /usr/bin/env python3
import sys
from pathlib import Path

pip_target_directory = Path(sys.argv[1])

init_file = pip_target_directory / 'NDATools/__init__.py'

with open(init_file, 'r') as f:
    contents = f.readlines()

for i, line in enumerate(contents):
    if line.startswith('import random, string'):
        update = False
        break
    if line.startswith('NDA_ORGINIZATION_ROOT_FOLDER'):
        index = i
        update = True
        break

if update:
    before = contents[:index]
    nda_line = [contents[index].replace("os.path.expanduser('~')", "'" + str(pip_target_directory) + "'")]
    after = contents[(index+1):]
    # new_lines = ['import random, string\n', "random_string = '_fasttrack2bids_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))\n"]
    new_contents = ''.join(before + nda_line + after)

    with open(init_file, 'w') as f:
        f.write(new_contents)

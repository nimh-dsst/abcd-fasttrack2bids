#! /usr/bin/env python3

import pandas
import sys
from glob import glob
from pathlib import Path

def main():
    # receive the bids root directory
    bids = Path(sys.argv[1]).resolve()

    # find all the scans_*.tsv files and combine them with pandas
    scans = pandas.concat([pandas.read_csv(f, sep='\t') for f in glob(f'{bids}/rawdata/scans_*.tsv')])

    # write the combined scans to a new file
    scans.to_csv(bids / 'rawdata/scans.tsv', sep='\t', index=False)

    # find all the bids_correction_log_*.tsv files and combine them with pandas
    corrections = pandas.concat([pandas.read_csv(f, sep='\t') for f in glob(f'{bids}/code/logs/bids_corrections_log_*.tsv')])

    # write the combined corrections to a new file
    corrections.to_csv(bids / 'code/logs/bids_corrections_log.tsv', sep='\t', index=False)

if __name__ == '__main__':
    main()
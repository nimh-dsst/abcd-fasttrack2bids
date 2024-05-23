#! /usr/bin/env python3

# The purpose of this script is to correct BIDS data in the outputs

# Importing the required libraries
import argparse
import json
import logging

from logging import debug, info, warning, error, critical
from pathlib import Path
from utilities import readable, available

# default logging basic configuration
logging.basicConfig(level=logging.INFO)

def cli():
    parser = argparse.ArgumentParser(description='Correct BIDS data')

    # very necessary arguments
    parser.add_argument('-b', '--bids', type=readable, required=True,
                        help='Path to the BIDS directory')
    parser.add_argument('-t', '--temporary', type=available, required=True,
                        help='Path to the output directory')
    parser.add_argument('-l', '--logs', type=available, required=True,
                        help='Path to the log file')

    # optional flag arguments
    parser.add_argument('--IntendedFor', action='store_true',
                        help='Assign IntendedFor fields using the DCAN-Labs/abcd-dicom2bids eta^2 technique')

    return parser.parse_args()

def main():
    pass

if __name__ == '__main__':
    main()

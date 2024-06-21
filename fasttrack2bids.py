#! /usr/bin/env python3

import argparse
import configparser

from logging import debug, info, warning, error, basicConfig
from nipype import Workflow
from nipype import Node
from nipype import MapNode
from nipype import Function
from nipype.interfaces.base import CommandLine
from pathlib import Path
from utilities import readable, available

# Define the command line
def cli():
    parser = argparse.ArgumentParser(description='Convert abcd_fastqc01 series all the way to BIDS format')

    parser.add_argument('abcd_fastqc01', type=readable, help='Path to abcd_fastqc01.txt file')
    parser.add_argument('bids_root', type=available, help='Path to place BIDS output directory')

    parser.add_argument(
        '-c', '--config', type=readable, required=True,
        help='Configuration file'
    )
    parser.add_argument(
        '-t', '--temporary-dir', type=available, required=True,
        help='Path to temporary directory'
    )

    # add a mutually exclusive group for either the CSV or the ignorable BIDS sessions
    input = parser.add_mutually_exclusive_group(required=True)
    input.add_argument(
        '-s', '--sessions-csv', type=readable,
        help='Path to sessions.csv file'
    )
    input.add_argument(
        '-i', '--ignore', type=readable,
        help='Path to already-existent BIDS ABCD sessions to ignore in this conversion round'
    )

    return parser.parse_args()

def read_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)

    return config

# Define the main function
def main():
    args = cli()
    config = read_config(args.config)

    # begin the nipype interfaces to call the three workflows as one big workflow
    fasttrack2s3 = Node(
        CommandLine('fasttrack2s3', args=f'-csv {args.sessions_csv} {args.abcd_fastqc01} {args.temporary_dir} {config['fasttrack2s3']['args']}'),
        name='fasttrack2s3'
    )

if __name__ == '__main__':
    main()

#! /usr/bin/env python3
#
# fasttrack2bids.py
# 
# This script should do the following:
#     1. Read the abcd_fastqc01.txt file and filter it by a sessions.csv file using fasttrack2s3.py
#     2. Generate an NIH HPC swarm file for running pipeline.py and then bids_corrections.py per session
#


# imports
import argparse
import configparser
import logging

from logging import debug, info, warning, error, critical
from nipype import Workflow
from nipype import Node
from nipype import MapNode
from nipype import Function
from nipype.interfaces.base import CommandLine
# from pipeline import collect_glob
from pathlib import Path
from utilities import readable, writable, available


# Get the path to the directory containing this script
HERE = Path(__file__).parent.resolve()

# Set up logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

# create help strings for the log level option
log_levels_str = "\n    ".join(LOG_LEVELS)


def read_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)

    return config


def generate_pipeline_args(argparse_args, s3links_folder, dcm2bids_config_file):
    from glob import glob
    from . import read_config

    config = read_config(argparse_args.config)
    base_arguments = f'-p {config['pipeline']['package_id']} -c {dcm2bids_config_file} -z LOGS BIDS --n-download 2 --n-unpack 2 --n-convert 1'
    s3link_files = sorted([t for t in glob(f'{s3links_folder}/*/*_s3links.txt')])

    arguments_list = []
    for s3link_file in s3link_files:
        arguments_list.append(f'{base_arguments} -o {argparse_args.temporary_dir} -s {s3link_file}')

    # @TODO turn arguments_list into a swarm file

    return arguments_list

# Define the command line interface
def cli():
    parser = argparse.ArgumentParser(description='Convert abcd_fastqc01 series all the way to BIDS format')

    parser.add_argument('abcd_fastqc01', type=readable, help='Path to abcd_fastqc01.txt file')
    parser.add_argument('bids_root', type=available, help='Path to place BIDS output directory')

    parser.add_argument(
        '-c', '--config', type=readable, required=True,
        help='Configuration file'
    )
    parser.add_argument(
        '-t', '--temporary-dir', type=writable, required=True,
        help='Path to temporary directory'
    )
    parser.add_argument(
        '-l', '--log-level', metavar='LEVEL',
        choices=LOG_LEVELS, default='INFO',
        help="Set the minimum logging level. Defaults to INFO.\n"
            "Options, in most to least verbose order, are:\n"
            f"    {log_levels_str}"
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


# Define the main function
def main():
    # Parse the command line
    args = cli()

    # Set up logging
    args.temporary_dir.joinpath('code/logs').mkdir(parents=True, exist_ok=True)
    log_filename = args.temporary_dir / 'code/logs/fasttrack2bids.log'

    if args.log_level == 'DEBUG':
        logging.basicConfig(filename=log_filename, filemode='a', format=LOG_FORMAT, level=logging.DEBUG)
    elif args.log_level == 'INFO':
        logging.basicConfig(filename=log_filename, filemode='a', format=LOG_FORMAT, level=logging.INFO)
    elif args.log_level == 'WARNING':
        logging.basicConfig(filename=log_filename, filemode='a', format=LOG_FORMAT, level=logging.WARNING)
    elif args.log_level == 'ERROR':
        logging.basicConfig(filename=log_filename, filemode='a', format=LOG_FORMAT, level=logging.ERROR)
    elif args.log_level == 'CRITICAL':
        logging.basicConfig(filename=log_filename, filemode='a', format=LOG_FORMAT, level=logging.CRITICAL)
    else:
        raise ValueError(f"Invalid log level: {args.log_level}")

    # read the configuration file
    config = read_config(args.config)

    filtered_s3links_folder = args.temporary_dir / 'filtered_abcd_fastqc01'
    filtered_s3links_folder.mkdir(parents=True, exist_ok=False)

    # begin the nipype interfaces to call the three workflows as one big workflow
    fasttrack2s3 = Node(
        CommandLine(f'poetry run --directory {HERE} python {HERE}/fasttrack2s3.py',
                    args=f'-csv {args.sessions_csv} {args.abcd_fastqc01} {filtered_s3links_folder} {config['fasttrack2s3']['options']}'),
        name='1_fasttrack2s3'
    )


    # pipeline_args Node
    # @TODO make "create_swarm_file" node here instead of in the generate_pipeline_args function
    pipeline_args = Node(
        Function(
            function=generate_pipeline_args,
            input_names=['argparse_args', 's3links_folder', 'dcm2bids_config_file'],
            output_names=['command_args']
        ),
        name='2_pipeline_args'
    )

    pipeline_args.inputs.argparse_args = args
    pipeline_args.inputs.s3links_folder = filtered_s3links_folder
    # @TODO make the following dcm2bids config file read from the config file
    pipeline_args.inputs.dcm2bids_config_file = HERE / 'dcm2bids_v3_config.json'


    # pipeline MapNode
    pipeline = MapNode(
        CommandLine(f'poetry run --directory {HERE} python {HERE}/pipeline.py'),
        iterfield=['args'],
        name='3_pipeline'
    )

    pipeline.inputs.args = pipeline_args.outputs.command_args


    # collect_bids_sessions = Node(
    #     Function(
    #         function=collect_glob,
    #             input_names=['pattern', 'mode'],
    #             output_names=['output_list']
    #     ),
    #     name='4_collect_bids_sessions'
    # )

    # collect_bids_sessions.inputs.pattern = f'{args.bids_root}/sub-*/ses-*'
    # collect_bids_sessions.inputs.mode = 'directories'

    # bids_corrections Node
    bids_corrections = Node(
        CommandLine(f'poetry run --directory {HERE} python {HERE}/bids_corrections.py',
                    args=f'-b {args.temporary_dir}/rawdata -l {args.temporary_dir}/code/logs -t {args.temporary_dir} {config['bids_corrections']['options']}'),
        name='5_bids_corrections'
    )


    # sync over the final BIDS data
    sync = Node(
        CommandLine('rsync -art', args=f'{args.temporary_dir}/* {args.bids_root}/'),
        name='6_rsync'
    )

    # create the workflow
    wf = Workflow(name='fasttrack2bids')
    wf.base_dir = args.temporary_dir


if __name__ == '__main__':
    main()

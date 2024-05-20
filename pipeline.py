#! /usr/bin/env python3

import argparse
import os
from glob import glob

from logging import debug, info, warning, error, basicConfig
from nipype import Workflow
from nipype import Node
from nipype import MapNode
from nipype import Function
from nipype.interfaces.base import CommandLine
from pathlib import Path

# Set up logging
basicConfig(level='INFO')

# assistant functions
def existent(path):
    """
    Check if a path exists
    :param path: Path to check
    :return: Existent path as a Path object
    """
    if not Path(path).exists():
        raise argparse.ArgumentTypeError(f"{path} does not exist")
    return Path(path).absolute()


def readable(path):
    """
    Check if a path is readable
    :param path: Path to check
    :return: Readable path as a Path object
    """
    if not os.access(path, os.R_OK):
        raise argparse.ArgumentTypeError(f"{path} is not readable")
    return Path(path).absolute()


def writable(path):
    """
    Check if a path is writable
    :param path: Path to check
    :return: Writable path as a Path object
    """
    if not os.access(path, os.W_OK):
        raise argparse.ArgumentTypeError(f"{path} is not writable")
    return Path(path).absolute()


def executable(path):
    """
    Check if a path is executable
    :param path: Path to check
    :return: Executable path as a Path object
    """
    if not os.access(path, os.X_OK):
        raise argparse.ArgumentTypeError(f"{path} is not executable")
    return Path(path).absolute()


def available(path):
    """
    Check if a path has a parent and is available to write to
    :param path: Path to check
    :return: Available path as a Path object
    """
    parent = Path(path).parent.resolve()
    if not (parent.exists() and os.access(str(parent), os.W_OK)):
        raise argparse.ArgumentTypeError(f"""{path} is either not writable or 
                                          the parent directory does not exist""")

    if Path(path).exists():
        return writable(path)
    else:
        return Path(path).absolute()


def cli():

    parser = argparse.ArgumentParser(description='Run the fasttrack2bids workflow')

    parser.add_argument('-p', '--package-id', type=int, required=True,
                        help='The package ID of the NDA ABCD Fast-Track dataset you already packaged')
    parser.add_argument('-s', '--input-s3-links', type=readable, required=True,
                        help='The path to the S3 links TXT file')
    parser.add_argument('-c', '--input-dcm2bids-config', type=readable, required=True,
                        help='The path to the Dcm2Bids config JSON file')
    parser.add_argument('-o', '--output-dir', type=available, required=True,
                        help='The output directory')
    parser.add_argument('-t', '--temporary-dir', type=writable,
                        help='The temporary intermediary files directory')
    parser.add_argument('-q', '--input-nda-fastqc', type=readable,
                        help='The path to the abcd_fastqc01.txt file')
    parser.add_argument('-z', '--preserve', choices=['LOGS', 'TGZ', 'DICOM', 'BIDS'], default=['BIDS'], nargs='+',
                        help='Select one or more file types to preserve, only BIDS is preserved by default')
    parser.add_argument('--n-download', type=int, default=1,
                        help='The number of downloadcmd worker threads to use')
    parser.add_argument('--n-unpack', type=int, default=1,
                        help='The number of tar xzf commands to run in parallel')
    parser.add_argument('--n-convert', type=int, default=1,
                        help='The number of dcm2bids conversion commands to run in parallel')

    return parser.parse_args()


def collect_glob(pattern, mode):
    from os.path import isfile, isdir
    from glob import glob

    if mode == 'files':
        glob_matches = [match for match in glob(pattern) if isfile(match)]
    elif mode == 'directories':
        glob_matches = [match for match in glob(pattern) if isdir(match)]
    else:
        raise ValueError(f"Invalid collect_glob mode: {mode}")

    return sorted(glob_matches)


def format_dcm2bids_args(bids_session_directory, config_file, output_dir):
    participant, session = bids_session_directory.split('/')[-2:]
    arguments = f'-p {participant} -s {session} -d {bids_session_directory} -c {config_file} -o {output_dir}'
    return arguments


def unpack_tgz(tgz_file, output_dir):
    import tarfile

    with tarfile.open(tgz_file, 'r:gz') as tar:
        tar.extractall(output_dir)
    
    return output_dir


def retrieve_task_events(input_root, output_root):
    import os
    import shutil

    task_dict = {
        'MID': [],
        'SST': [],
        'nback': []
    }

    if output_root.endswith('sourcedata'):
        print('WARNING: output_root should not end with sourcedata, correcting...')
        bids_root = os.path.abspath(output_root.replace('sourcedata', '').rstrip('/'))
    else:
        bids_root = os.path.abspath(output_root)

    for root, dirs, files in os.walk(input_root):
        if not root.endswith('func'):
            continue
        for file in files:
            if 'EventRelatedInformation.' in file:        
                if 'MID' in file:
                    task = 'MID'
                elif 'SST' in file:
                    task = 'SST'
                elif 'nBack' in file:
                    task = 'nback'
                else:
                    print(f'ERROR: Unknown task in {file}')

                task_dict[task].append(os.path.join(root, file))

    for task in task_dict:
        task_list = sorted(task_dict[task])

        for i, task_file in enumerate(task_list):
            fileparts = task_file.split('/')
            subject = fileparts[-4]
            session = fileparts[-3]
            run = i + 1
            ext = task_file.split('.')[-1]

            output_path = f'{bids_root}/sourcedata/{subject}/{session}/func/{subject}_{session}_task-{task}_run-{run:02}_bold_EventRelatedInformation.{ext}'
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            shutil.copy(task_file, output_path)

    return


def main():
    # Parse the command line arguments
    args = cli()
    pipeline_suffix = str(args.input_s3_links.stem.replace("_s3links", ""))

    # check if the temporary directory is provided
    if args.temporary_dir != None:
        output_dir = f'{args.temporary_dir}/{pipeline_suffix}'
    else:
        output_dir = f'{args.output_dir}/{pipeline_suffix}'

    cleanup_dir = args.output_dir

    # initialize the inputs
    dcm2bids_config_json = str(args.input_dcm2bids_config)
    output_tgz_root = f'{output_dir}/TGZ'
    output_dicom_root = f'{output_dir}/DICOM'
    output_bids_root = f'{output_dir}/BIDS'
    pipeline_base_dir = f'{output_dir}/pipeline'

    if args.preserve == ['LOGS']:
        error('Only the LOGS option was selected to be preserved. You MUST choose to preserve something besides LOGS to produce files.')
        return
    else:

        # make the TGZ directory
        mkdir_tgz = Node(
            CommandLine('mkdir', args=f'-p {output_tgz_root}'),
            name='mkdir_tgz')

        # download the TGZ files
        downloadcmd = Node(
            CommandLine('downloadcmd',
                args=f'-dp {args.package_id} -t {str(args.input_s3_links)} -d {output_tgz_root} --workerThreads {args.n_download}'),
            name='downloadcmd')

        ### Create the NDA TGZ downloading workflow ###
        download_wf = Workflow(
            name="download",
            base_dir=pipeline_base_dir,
        )

        download_wf.add_nodes([
            mkdir_tgz,
            downloadcmd,
        ])

        download_wf.connect([
            (mkdir_tgz, downloadcmd, []),
        ])

        # Run the download workflow
        download_wf.write_graph("download.dot")
        download_results = download_wf.run(plugin='MultiProc', plugin_args={'n_procs' : args.n_download})
        debug(download_results)

    # decide whether or not to continue with the unpacking
    if args.preserve == ['TGZ']:
        warning('DICOM and BIDS intermediary files are not to be preserved and will not be produced.')
        return
    else:

        # make the DICOM directory
        mkdir_dicom = Node(
            CommandLine('mkdir', args=f'-p {output_dicom_root}'),
            name='mkdir_dicom')

        # collect the input DICOM sessions
        collect_tgzs = Node(
            Function(
                function=collect_glob,
                input_names=['pattern', 'mode'],
                output_names=['output_list']
            ),
            name='collect_tgzs')

        collect_tgzs.inputs.pattern = f'{output_tgz_root}/image03/*.tgz'
        collect_tgzs.inputs.mode = 'files'

        # unpack the TGZ files
        unpack_tgz_node = MapNode(
            Function(
                function=unpack_tgz,
                input_names=['tgz_file', 'output_dir'],
                output_names=['output_dir']
            ),
            iterfield=['tgz_file'],
            name='unpack_tgz')
        
        unpack_tgz_node.inputs.output_dir = output_dicom_root
        
        ### Create the TGZ unpacking workflow ###
        unpack_wf = Workflow(
            name="unpack",
            base_dir=pipeline_base_dir,
        )

        unpack_wf.add_nodes([
            mkdir_dicom,
            collect_tgzs,
            unpack_tgz_node,
        ])

        unpack_wf.connect([
            (mkdir_dicom, collect_tgzs, []),
            (collect_tgzs, unpack_tgz_node, [('output_list', 'tgz_file')]),
        ])

        # Run the unpacking workflow
        unpack_wf.write_graph("unpack.dot")
        unpack_results = unpack_wf.run(plugin='MultiProc', plugin_args={'n_procs' : args.n_unpack})
        debug(unpack_results)


    # decide whether or not to continue with the conversion
    if 'BIDS' not in args.preserve:
        warning('BIDS files are not to be preserved and so will not be produced.')
        return
    else:

        ### Create the DICOM to BIDS conversion workflow ###
        # make the BIDS directory
        mkdir_bids = Node(
            CommandLine('mkdir', args=f'-p {output_bids_root}'),
            name='mkdir_bids')

        # collect the input DICOM sessions
        collect_dicom_sessions = Node(
            Function(
                function=collect_glob,
                input_names=['pattern', 'mode'],
                output_names=['output_list']
            ),
            name='collect_dicom_sessions')

        collect_dicom_sessions.inputs.pattern = f'{output_dicom_root}/sub-*/ses-*'
        collect_dicom_sessions.inputs.mode = 'directories'

        # setup for the DICOM to BIDS conversion
        format_args = MapNode(
            Function(
                function=format_dcm2bids_args,
                input_names=['bids_session_directory', 'config_file', 'output_dir'],
                output_names=['arguments']
            ),
            iterfield=['bids_session_directory'],
            name='format_args')

        format_args.inputs.config_file = dcm2bids_config_json
        format_args.inputs.output_dir = output_bids_root

        # DICOM to BIDS conversion MapNode
        dcm2bids = MapNode(
            CommandLine('dcm2bids'),
            iterfield=['args'],
            name='dcm2bids')

        ### Create the DICOM to BIDS conversion workflow ###
        convert_wf = Workflow(
            name="convert",
            base_dir=pipeline_base_dir,
        )

        convert_wf.add_nodes([
            mkdir_bids,
            collect_dicom_sessions,
            format_args,
            dcm2bids
        ])

        convert_wf.connect([
            (mkdir_bids, collect_dicom_sessions, []),
            (collect_dicom_sessions, format_args, [('output_list', 'bids_session_directory')]),
            (format_args, dcm2bids, [('arguments', 'args')]),
        ])

        # Run the conversion workflow
        convert_wf.write_graph("convert.dot")
        convert_results = convert_wf.run(plugin='MultiProc', plugin_args={'n_procs' : args.n_convert})
        debug(convert_results)


    if 'BIDS' in args.preserve:
        # make the BIDS rawdata output directory
        mkdir_bids = Node(
            CommandLine('mkdir', args=f'-p {cleanup_dir}/rawdata'),
            name='mkdir_bids')
        mkdir_bids_results = mkdir_bids.run()
        debug(mkdir_bids_results)

        # move the BIDS files to the output directory
        rsync_bids = Node(
            CommandLine('rsync', args=f'-art {output_bids_root}/sub-* {cleanup_dir}/rawdata/'),
            name='rsync_bids')
        rsync_bids_results = rsync_bids.run()
        debug(rsync_bids_results)

        # retrieve the task events
        task_events = Node(
            Function(
                function=retrieve_task_events,
                input_names=['input_root', 'output_root']
            ),
            name='task_events')
        task_events.inputs.input_root = output_dicom_root
        task_events.inputs.output_root = cleanup_dir
        task_events_results = task_events.run()
        debug(task_events_results)

        if 'LOGS' in args.preserve:
            # make the BIDS LOGS output directory
            mkdir_bids_logs = Node(
                CommandLine('mkdir', args=f'-p {cleanup_dir}/code/tmp_dcm2bids/log'),
                name='mkdir_bids_logs')
            mkdir_bids_logs_results = mkdir_bids_logs.run()
            debug(mkdir_bids_logs_results)

            # move the LOG files to the output directory
            rsync_bids_logs = Node(
                CommandLine('rsync', args=f'-art {output_bids_root}/tmp_dcm2bids/log/*.log {cleanup_dir}/code/tmp_dcm2bids/log/'),
                name='rsync_bids_logs')
            rsync_bids_logs_results = rsync_bids_logs.run()
            debug(rsync_bids_logs_results)

    if 'DICOM' in args.preserve:
        # make the DICOM sourcedata output directory
        mkdir_sddicom = Node(
            CommandLine('mkdir', args=f'-p {cleanup_dir}/sourcedata/DICOM'),
            name='mkdir_sdtgz')
        mkdir_sddicom_results = mkdir_sddicom.run()
        debug(mkdir_sddicom_results)

        # move the DICOM files to the output directory
        rsync_dicom = Node(
            CommandLine('rsync', args=f'-art {output_dicom_root}/* {cleanup_dir}/sourcedata/DICOM/'),
            name='rsync_dicom')
        rsync_dicom_results = rsync_dicom.run()
        debug(rsync_dicom_results)

    if 'TGZ' in args.preserve:
        # make the TGZ sourcedata output directory
        mkdir_sdtgz = Node(
            CommandLine('mkdir', args=f'-p {cleanup_dir}/sourcedata/TGZ'),
            name='mkdir_sdtgz')
        mkdir_sdtgz_results = mkdir_sdtgz.run()
        debug(mkdir_sdtgz_results)

        # move the TGZ files to the output directory
        rsync_tgz = Node(
            CommandLine('rsync', args=f'-art {output_tgz_root}/* {cleanup_dir}/sourcedata/TGZ/'),
            name='rsync_tgz')
        rsync_tgz_results = rsync_tgz.run()
        debug(rsync_tgz_results)


    if 'LOGS' in args.preserve:
        # make the LOGS output directory
        mkdir_logs = Node(
            CommandLine('mkdir', args=f'-p {cleanup_dir}/code/{pipeline_suffix}'),
            name='mkdir_logs')
        mkdir_logs_results = mkdir_logs.run()
        debug(mkdir_logs_results)

        # move the LOG files to the output directory
        rsync_logs = Node(
            CommandLine('rsync', args=f'-art {pipeline_base_dir}/download {pipeline_base_dir}/unpack {pipeline_base_dir}/convert {cleanup_dir}/code/{pipeline_suffix}/'),
            name='rsync_logs')
        rsync_logs_results = rsync_logs.run()
        debug(rsync_logs_results)


    if args.temporary_dir != None:
        # remove the temporary directory
        rm_tmp = Node(
            CommandLine('rm', args=f'-rf {args.temporary_dir}/{pipeline_suffix}'),
            name='rm_tmp')
    else:
        rm_tmp = Node(
            CommandLine('rm', args=f'-rf {args.output_dir}/{pipeline_suffix}'),
            name='rm_tmp')

    rm_tmp_results = rm_tmp.run()
    debug(rm_tmp_results)


if __name__ == '__main__':
    main()

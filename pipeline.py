#! /usr/bin/env python3

import argparse
import logging
import os
import random
import string

from logging import debug, info, warning, error, critical
from nipype import Workflow
from nipype import Node
from nipype import MapNode
from nipype import Function
from nipype.interfaces.base import CommandLine
from utilities import readable, available, writable

# Set up logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

# create help string for the log level option
log_levels_str = "\n    ".join(LOG_LEVELS)


def cli():

    parser = argparse.ArgumentParser(description='Run the fasttrack2bids workflow')

    parser.add_argument('-p', '--package-id', type=int, required=True,
                        help='The package ID of the NDA ABCD Fast-Track dataset you already packaged')
    parser.add_argument('-s', '--input-s3-links', type=readable, required=True,
                        help='The path to the S3 links TXT file')
    parser.add_argument('-c', '--input-dcm2bids-config', type=readable, required=True,
                        help='The path to the Dcm2Bids config JSON file')
    parser.add_argument('-o', '--output-dir', type=writable, required=True,
                        help='The output directory')
    parser.add_argument('-t', '--temporary-dir', type=writable,
                        help='The temporary intermediary files directory')
    parser.add_argument('-z', '--preserve', choices=['LOGS', 'TGZ', 'DICOM', 'BIDS'], default=['BIDS'], nargs='+',
                        help='Select one or more file types to preserve, only BIDS is preserved by default')
    parser.add_argument('-n', '--n-all', type=int, default=1,
                        help='The number of parallel commands to use for all three')
    parser.add_argument('--n-download', type=int, default=1,
                        help='The number of downloadcmd worker threads to use')
    parser.add_argument('--n-unpack', type=int, default=1,
                        help='The number of tar xzf commands to run in parallel')
    parser.add_argument('--n-convert', type=int, default=1,
                        help='The number of dcm2bids conversion commands to run in parallel')
    parser.add_argument('-l', '--log-level', metavar='LEVEL',
                        choices=LOG_LEVELS, default='INFO',
                        help="Set the minimum logging level. Defaults to INFO.\n"
                            "Options, in most to least verbose order, are:\n"
                            f"    {log_levels_str}")
    parser.add_argument('-d', '--disable-workaround', action='store_true',
                        help='By default (when present), a "corrupt volume" in any func run '
                            'DICOM series [where the first DICOM contains "=RawDataStorage" '
                            'in field (0002,0002)] is deleted after unpacking and before '
                            'conversion to BIDS. This flag disables that default feature in '
                            'order to preserve the "corrupt volume" DICOMs. This flag will '
                            'make dcm2niix fail.')

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


def corrupt_volume_check(func_dcm):
    import os
    import pydicom

    dicom_one_meta = pydicom.dcmread(func_dcm)

    if dicom_one_meta.file_meta.MediaStorageSOPClassUID.name == 'Raw Data Storage':
        func_run = os.path.dirname(func_dcm)

    else:
        func_run = ''

    return func_run


def corrupt_volume_removal(func_run):

    def rename_scan(series):
        import re
        from pathlib import Path

        scan = Path(series)
        basename = scan.name
        funcdir = scan.parent
        if 'rsfMRI' in basename:
            task = 'rest'
        elif 'MID' in basename:
            task = 'MID'
        elif 'SST' in basename:
            task = 'SST'
        elif 'nBack' in basename:
            task = 'nback'

        glob_expression = re.sub(r'_run-\d+', '_run-*', str(basename))
        scans = sorted([str(x) for x in funcdir.glob(glob_expression) if x.is_dir()])
        for i, scandir in enumerate(scans):
            run = i + 1
            if scandir == str(scan):
                break

        subsesdir = str(funcdir.parent)
        subject = subsesdir.split('/')[-2]
        session = subsesdir.split('/')[-1]
        newname = f'{subject}/{session}/func/{subject}_{session}_task-{task}_run-{run:02}_bold.nii.gz'

        return newname

    import os
    import pydicom
    from glob import glob

    if func_run == '':
        return False

    else:
        # rename the scan to the BIDS format for scans.tsv
        alt_name = rename_scan(func_run)

        # in dicom_one, grab the number of temporal positions (2001,1081) and check the number of slices per time point is 60
        dicom_one = glob(f'{func_run}/*_dicom000001.dcm')[0]
        dicom_one_meta = pydicom.dcmread(dicom_one)
        num_temporal_positions = int(dicom_one_meta[0x2001,0x1081].value)
        func_run_dicoms = [dicom for dicom in glob(f'{func_run}/*.dcm')]

        # if the number of slices per time point is not 60, print an error message
        if num_temporal_positions * 60 != len(func_run_dicoms):
            raise ValueError(f'ERROR: {func_run} has {len(func_run_dicoms)} DICOMs, but {num_temporal_positions} temporal positions X 60 does not equal {len(func_run_dicoms)}')

        # remove the entire first corrupt volume by removing 60 slices
        dicom_one_basename = os.path.basename(dicom_one)
        for i in range(60):
            dicom_num = str( (i * num_temporal_positions) + 1 ).zfill(6)
            dicom_basename = dicom_one_basename.replace('000001', dicom_num)
            os.remove(os.path.join(func_run, dicom_basename))
        
        # go to the parent folder of the DICOM folder and create a scans.tsv
        root_relpath = '/'.join(func_run.split('/')[:-5])
        scans_file = f'{root_relpath}/scans.tsv'

        if not os.path.exists(scans_file):
            with open(scans_file, 'w') as f:
                f.write('filename\tcorrupt_volume\n')
            print(f'Creating "scans.tsv": {scans_file}')

        with open(scans_file, 'a') as f:
            f.write(f'{alt_name}\t1\n')

        return True


def retrieve_task_events(input_root, output_root):
    import os
    import shutil
    from pathlib import Path

    if str(Path(output_root)).endswith('sourcedata'):
        print('WARNING: output_root should not end with sourcedata, correcting...')
        bids_root = str(Path(output_root).resolve().replace('sourcedata', '').rstrip('/'))
    else:
        bids_root = str(Path(output_root).resolve())

    collection = {}

    for root, dirs, files in os.walk(str(Path(input_root).resolve())):
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

                sub = root.split('/')[-3]
                ses = root.split('/')[-2]

                if sub not in collection:
                    collection[sub] = {}
                if ses not in collection[sub]:
                    collection[sub][ses] = {}
                if task not in collection[sub][ses]:
                    collection[sub][ses][task] = []

                collection[sub][ses][task].append(os.path.join(root, file))

    for sub in collection:
        for ses in collection[sub]:
            for task in collection[sub][ses]:
                task_list = sorted(collection[sub][ses][task])

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

    # Set up logging
    if args.log_level == 'DEBUG':
        logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG)
    elif args.log_level == 'INFO':
        logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
    elif args.log_level == 'WARNING':
        logging.basicConfig(format=LOG_FORMAT, level=logging.WARNING)
    elif args.log_level == 'ERROR':
        logging.basicConfig(format=LOG_FORMAT, level=logging.ERROR)
    elif args.log_level == 'CRITICAL':
        logging.basicConfig(format=LOG_FORMAT, level=logging.CRITICAL)
    else:
        raise ValueError(f"Invalid log level: {args.log_level}")

    # set the pipeline suffix from the input S3 links file
    pipeline_suffix = str(args.input_s3_links.stem.replace("_s3links", ""))

    # check if the temporary directory is provided
    if args.temporary_dir != None:
        output_dir = f'{args.temporary_dir}/{pipeline_suffix}'
    else:
        output_dir = f'{args.output_dir}/{pipeline_suffix}'

    # assign the cleanup directory
    cleanup_dir = args.output_dir

    # set the number of parallel commands to use for all three
    if args.n_all > 1:
        warning(f'Using parallel setting of {args.n_all} for all stages')
        n_download = args.n_all
        n_unpack = args.n_all
        n_convert = args.n_all
    else:
        n_download = args.n_download
        n_unpack = args.n_unpack
        n_convert = args.n_convert

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
                args=f'-dp {args.package_id} -t {str(args.input_s3_links)} -d {output_tgz_root} --workerThreads {n_download}'),
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
        download_results = download_wf.run()
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
        unpack_results = unpack_wf.run(plugin='MultiProc', plugin_args={'n_procs' : n_unpack})
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

        # as long as the workaround is not disabled, remove the corrupt volumes
        if not args.disable_workaround:
            # collect all func DICOM 1's
            collect_func_dcms = Node(
                Function(
                    function=collect_glob,
                    input_names=['pattern', 'mode'],
                    output_names=['output_list']
                ),
                name='collect_func_dcms')

            collect_func_dcms.inputs.pattern = f'{output_dicom_root}/sub-*/ses-*/func/*/*_dicom000001.dcm'
            collect_func_dcms.inputs.mode = 'files'

            # check for corrupt volumes
            check_corrupt_volumes = MapNode(
                Function(
                    function=corrupt_volume_check,
                    input_names=['func_dcm'],
                    output_names=['func_run']
                ),
                iterfield=['func_dcm'],
                name='check_corrupt_volumes')

            # remove any found corrupt volumes
            remove_corrupt_volume = MapNode(
                Function(
                    function=corrupt_volume_removal,
                    input_names=['func_run'],
                    output_names=['is_corrected']
                ),
                iterfield=['func_run'],
                name='remove_corrupt_volume')

            # define workaround workflow
            workaround_wf = Workflow(
                name="workaround",
                base_dir=pipeline_base_dir,
            )

            workaround_wf.add_nodes([
                collect_func_dcms,
                check_corrupt_volumes,
                remove_corrupt_volume
            ])

            workaround_wf.connect([
                (collect_func_dcms, check_corrupt_volumes, [('output_list', 'func_dcm')]),
                (check_corrupt_volumes, remove_corrupt_volume, [('func_run', 'func_run')])
            ])

            # Run the workaround workflow
            workaround_wf.write_graph("workaround.dot")
            workaround_results = workaround_wf.run(plugin='MultiProc', plugin_args={'n_procs' : n_convert})
            debug(workaround_results)

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
        convert_results = convert_wf.run(plugin='MultiProc', plugin_args={'n_procs' : n_convert})
        debug(convert_results)


    if 'BIDS' in args.preserve:
        # make the BIDS rawdata output directory
        mkdir_bids = Node(
            CommandLine('mkdir', args=f'-p {cleanup_dir}/rawdata'),
            name='mkdir_bids')
        mkdir_bids_results = mkdir_bids.run()
        debug(mkdir_bids_results)

        # retrieve the scans.tsv file if it's there and uniquely identify it
        scans_tsv = f'{output_dir}/scans.tsv'
        if os.path.exists(scans_tsv):
            temp_string = ''.join(random.choices(string.ascii_uppercase + '123456789', k=8))
            scans_tsv_unique = f'{cleanup_dir}/rawdata/scans_{temp_string}.tsv'
            rsync_scans = Node(
                CommandLine('rsync', args=f'-art {scans_tsv} {scans_tsv_unique}'),
                name='rsync_scans')
            rsync_scans_results = rsync_scans.run()
            debug(rsync_scans_results)

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
                CommandLine('mkdir', args=f'-p {cleanup_dir}/code/logs/tmp_dcm2bids/log'),
                name='mkdir_bids_logs')
            mkdir_bids_logs_results = mkdir_bids_logs.run()
            debug(mkdir_bids_logs_results)

            # move the LOG files to the output directory
            rsync_bids_logs = Node(
                CommandLine('rsync', args=f'-art {output_bids_root}/tmp_dcm2bids/log/*.log {cleanup_dir}/code/logs/tmp_dcm2bids/log/'),
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
            CommandLine('mkdir', args=f'-p {cleanup_dir}/code/logs/{pipeline_suffix}'),
            name='mkdir_logs')
        mkdir_logs_results = mkdir_logs.run()
        debug(mkdir_logs_results)

        # sync the LOG files to the output directory
        rsync_logs = Node(
            CommandLine('rsync', args=f'-art {pipeline_base_dir}/download {pipeline_base_dir}/unpack {pipeline_base_dir}/convert {cleanup_dir}/code/logs/{pipeline_suffix}/'),
            name='rsync_logs')
        rsync_logs_results = rsync_logs.run()
        debug(rsync_logs_results)

        if not args.disable_workaround:
            # sync the workaround LOG files to the output directory
            rsync_workaround = Node(
                CommandLine('rsync', args=f'-art {pipeline_base_dir}/workaround {cleanup_dir}/code/logs/{pipeline_suffix}/'),
                name='rsync_workaround')
            rsync_workaround_results = rsync_workaround.run()
            debug(rsync_workaround_results)


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

#! /usr/bin/env python3


import argparse
import os
import pydra
from glob import glob
from pathlib import Path


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
    parser.add_argument('--n-download', type=int, default=1,
                        help='The number of downloadcmd worker threads to use')
    parser.add_argument('--n-unpack', type=int, default=1,
                        help='The number of tar xzf commands to run in parallel')
    parser.add_argument('--n-convert', type=int, default=1,
                        help='The number of dcm2bids conversion commands to run in parallel')

    return parser.parse_args()


@pydra.mark.task
@pydra.mark.annotate(
    {
        'pattern': str,
        'mode': str,
        'return': {
            'collection': list
        }
    }
)
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


@pydra.mark.task
@pydra.mark.annotate(
    {
        'bids_session_directory': str,
        'config_file': str,
        'output_dir': str,
        'return': {
            'args_list': list
        }
    }
)
def format_dcm2bids_args(bids_session_directory, config_file, output_dir):
    participant, session = bids_session_directory.split('/')[-2:]
    args_list = f'-p {participant} -s {session} -d {bids_session_directory} -c {config_file} -o {output_dir}'.split(' ')
    return args_list


@pydra.mark.task
@pydra.mark.annotate(
    {
        'tgz_file': str,
        'output_dir': str,
        'return': {
            'output_dir': str
        }
    }
)
def unpack_tgz(tgz_file, output_dir):
    import tarfile

    with tarfile.open(tgz_file, 'r:gz') as tar:
        tar.extractall(output_dir)
    
    return output_dir


def main():
    # Parse the command line arguments
    args = cli()


    # ### Create the NDA TGZ downloading workflow ###
    # download_wf = pydra.Workflow(
    #     name="download",
    #     input_spec=[
    #         'input_s3_links',
    #         'fasttrack_package_id',
    #         'n_download',
    #         'output_tgz_root'
    #     ],
    #     audit_flags=pydra.utils.messenger.AuditFlag.ALL,
    #     messengers=pydra.utils.messenger.PrintMessenger()
    # )
    # download_wf.inputs.input_s3_links = str(args.input_s3_links)
    # download_wf.inputs.fasttrack_package_id = args.package_id
    # download_wf.inputs.n_download = args.n_download
    # if args.temporary_dir != None:
    #     download_wf.inputs.output_tgz_root = f'{args.temporary_dir}/TGZ'
    # else:
    #     download_wf.inputs.output_tgz_root = f'{args.output_dir}/TGZ'

    # download_wf.add(
    #     pydra.ShellCommandTask(
    #         name='setup_tgz_dir',
    #         executable='mkdir',
    #         args=f'-p {download_wf.inputs.output_tgz_root}'.split(' ')
    #     )
    # )

    # download_wf.add(
    #     pydra.ShellCommandTask(
    #         name='download',
    #         executable='downloadcmd',
    #         args=f'-dp {download_wf.inputs.fasttrack_package_id} -t {download_wf.inputs.input_s3_links} -d {download_wf.inputs.output_tgz_root} --workerThreads {download_wf.inputs.n_download}'.split(' ')
    #     )
    # )

    # download_wf.add(
    #     collect_glob(
    #         name='collect_tgzs',
    #         pattern=f'{download_wf.inputs.output_tgz_root}/image03/*.tgz',
    #         mode='files'
    #     )
    # )

    # download_wf.set_output(
    #     [
    #         ('output_tgzs', download_wf.collect_tgzs.lzout.collection)
    #     ]
    # )

    # # Run the download workflow
    # with pydra.Submitter(plugin='cf', n_procs=args.n_download) as submitter:
    #     submitter(download_wf)

    # download_results = download_wf.result()
    # print(download_results)


    # ### Create the TGZ unpacking workflow ###
    # unpack_wf = pydra.Workflow(
    #     name="unpack",
    #     input_spec=[
    #         'input_tgz_root',
    #         'input_tgzs',
    #         'output_dicom_root'
    #     ],
    #     audit_flags=pydra.utils.messenger.AuditFlag.ALL,
    #     messengers=pydra.utils.messenger.PrintMessenger()
    # )
    # unpack_wf.inputs.input_tgzs = download_results.output.output_tgzs
    # if args.temporary_dir != None:
    #     unpack_wf.inputs.input_tgz_root = f'{args.temporary_dir}/TGZ'
    #     unpack_wf.inputs.output_dicom_root = f'{args.temporary_dir}/DICOM'
    # else:
    #     unpack_wf.inputs.input_tgz_root = f'{args.output_dir}/TGZ'
    #     unpack_wf.inputs.output_dicom_root = f'{args.output_dir}/DICOM'

    # unpack_wf.add(
    #     pydra.ShellCommandTask(
    #         name='setup_dicom_dir',
    #         executable='mkdir',
    #         args=f'-p {unpack_wf.inputs.output_dicom_root}'.split(' ')
    #     )
    # )

    # unpack_wf.split('input_tgzs', input_tgzs=unpack_wf.inputs.input_tgzs)
    # unpack_wf.add(
    #     unpack_tgz(
    #         name='unpack_tgz',
    #         tgz_file=unpack_wf.lzin.input_tgzs,
    #         output_dir=unpack_wf.inputs.output_dicom_root
    #     )
    # )
    # unpack_wf.combine('input_tgzs')

    # unpack_wf.add(
    #     collect_glob(
    #         name='collect_dicom_sessions',
    #         pattern=f'{unpack_wf.inputs.output_dicom_root}/sub-*/ses-*',
    #         mode='directories'
    #     )
    # )

    # unpack_wf.set_output(
    #     [
    #         ('output_dicom_sessions', unpack_wf.collect_dicom_sessions.lzout.collection)
    #     ]
    # )

    # # Run the unpack workflow
    # with pydra.Submitter(plugin='cf', n_procs=args.n_unpack) as submitter:
    #     submitter(unpack_wf)

    # unpack_results = unpack_wf.result()
    # print(unpack_results)


    ### Create the DICOM to BIDS conversion workflow ###
    convert_wf = pydra.Workflow(
        name="convert",
        input_spec=[
            'input_sessions_list'
        ],
        audit_flags=pydra.utils.messenger.AuditFlag.ALL,
        messengers=pydra.utils.messenger.PrintMessenger()
    )
    dcm2bids_config_json = str(args.input_dcm2bids_config)
    if args.temporary_dir != None:
        input_dicom_root = f'{args.temporary_dir}/DICOM'
        output_bids_root = f'{args.temporary_dir}/BIDS'
    else:
        input_dicom_root = f'{args.output_dir}/DICOM'
        output_bids_root = f'{args.output_dir}/BIDS'

    convert_wf.add(
        pydra.ShellCommandTask(
            name='setup_bids_dir',
            executable='mkdir',
            args=f'-p {output_bids_root}'.split(' ')
        )
    )

    convert_wf.add(
        collect_glob(
            name='collect_dicom_sessions',
            pattern=f'{input_dicom_root}/sub-*/ses-*/',
            mode='directories'
        )
    )

    input_sessions_list = glob(f'{input_dicom_root}/sub-*/ses-*/')
    convert_wf.split('input_sessions_list', input_sessions_list=input_sessions_list)
    convert_wf.add(
        format_dcm2bids_args(
            name='format_args',
            bids_session_directory=convert_wf.lzin.input_sessions_list,
            config_file=dcm2bids_config_json,
            output_dir=output_bids_root
        )
    )

    convert_wf.add(
        pydra.ShellCommandTask(
            name='dcm2bids',
            executable='dcm2bids',
            args=convert_wf.format_args.lzout.args_list
        )
    )
    convert_wf.combine('input_sessions_list')

    convert_wf.add(
        collect_glob(
            name='collect_bids_sessions',
            pattern=f'{output_bids_root}/sub-*/ses-*/',
            mode='directories'
        )
    )

    convert_wf.set_output(
        [
            ('output_bids_sessions', convert_wf.collect_bids_sessions.lzout.collection)
        ]
    )

    # Run the conversion workflow
    with pydra.Submitter(plugin='cf', n_procs=args.n_convert) as submitter:
        submitter(convert_wf)

    dcm2bids_results = convert_wf.result()
    print(dcm2bids_results)


    if args.temporary_dir == None:
        return
    else:
        pass

    ### Create the BIDS move and clean workflow ###
    cleanup_wf = pydra.Workflow(
        name="cleanup",
        input_spec=[
            'temporary_dir',
            'output_bids_root'
        ],
        audit_flags=pydra.utils.messenger.AuditFlag.ALL,
        messengers=pydra.utils.messenger.PrintMessenger()
    )
    cleanup_wf.inputs.temporary_dir = args.temporary_dir
    cleanup_wf.inputs.output_bids_root = args.output_dir

    # Copy the BIDS directory to the output directory
    cleanup_wf.add(
        pydra.ShellCommandTask(
            name='move_bids',
            executable='mv',
            args=f'{cleanup_wf.lzin.temporary_dir}/BIDS/* {cleanup_wf.lzin.output_bids_root}/'.split(' ')
        )
    )

    # Clean up
    cleanup_wf.add(
        pydra.ShellCommandTask(
            name='cleanup',
            executable='rm',
            args=f'-rf {cleanup_wf.lzin.temporary_dir}/BIDS {cleanup_wf.lzin.temporary_dir}/DICOM {cleanup_wf.lzin.temporary_dir}/TGZ'.split(' ')
        )
    )

    cleanup_wf.set_output(
        [
            ('output_bids_root', cleanup_wf.lzin.output_bids_root)
        ]
    )

    # Run the move and clean workflow
    with pydra.Submitter(plugin='cf') as submitter:
        submitter(cleanup_wf)

    cleanup_results = cleanup_wf.result()
    print(cleanup_results)

    return



if __name__ == '__main__':
    main()

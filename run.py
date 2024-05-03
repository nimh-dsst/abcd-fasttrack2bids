#! /usr/bin/env python3


import argparse
import pydra
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
    parser.add_argument('-q', '--input-nda-fastqc', type=readable,
                        help='The path to the abcd_fastqc01.txt file')
    parser.add_argument('--n-download', type=int, default=1,
                        help='The number of downloadcmd worker threads to use')
    parser.add_argument('--n-unpack', type=int, default=1,
                        help='The number of tar xzf commands to run in parallel')
    parser.add_argument('--n-dcm2bids', type=int, default=1,
                        help='The number of dcm2bids commands to run in parallel')

    return parser.parse_args()


@pydra.mark.task
def collect_glob(pattern, mode):
    from os.path import isfile, isdir
    from glob import glob

    if mode == 'files':
        glob_matches = [match for match in glob(pattern) if isfile(match)]
    elif mode == 'directories':
        glob_matches = [match for match in glob(pattern) if isdir(match)]
    else:
        raise ValueError(f"Invalid collect_glob mode: {mode}")

    return sorted(list(glob_matches))


@pydra.mark.task
def format_dcm2bids_args(bids_session_directory, config_file, output_dir):
    participant, session = bids_session_directory.split('/')[-2:]
    args_list = f'-p {participant} -s {session} -c {config_file} -o {output_dir}'.split(' ')
    return args_list


def main():
    # Parse the command line arguments
    args = cli()


    # # Add the fasttrack2s3 task to the workflow
    # task1 = pydra.ShellCommandTask(
    #     name='filter',
    #     executable='python3',
    #     args=f'{HERE}/fasttrack2s3.py {input_fastqc_file} {args.output_dir} -d {" ".join(datatypes)}'.split(' '),
    # )


    # # Add the collection of TGZ files task to the workflow
    # task3 = collect_glob(pattern=f'{args.output_dir}/TGZ/*.tgz', mode='files')


    # # Add the unpack task to the workflow
    # task4 = pydra.ShellCommandTask(
    #     name='unpack',
    #     executable='tar',
    #     args=f'-xzf {WHAT_GOES_HERE} -C {args.output_dir}/DICOM'.split(' ')
    # )


    # # Add the collection of BIDS sessions task to the workflow
    # task5 = collect_glob(pattern=f'{args.output_dir}/DICOM/sub-*/ses-*', mode='directories')


    # # Add BIDS participant and session extraction task to the workflow
    # task6 = parse_bids_session(bids_session_directory=HOWS_THIS_WORK)


    # # Add the dcm2bids task to the workflow
    # task7 = pydra.ShellCommandTask(
    #     name='dcm2bids',
    #     executable='dcm2bids',
    #     args=f'-p {task6.lzout.participant} -s {task6.lzout.session} -c {args.output_dir}/dcm2bids_v3_config.json -o {args.output_dir}/BIDS'.split(' ')
    # )


    # Create the NDA TGZ downloading workflow
    download_wf = pydra.Workflow(
        name="s32tgz",
        input_spec=[
            'input_s3_links',
            'fasttrack_package_id',
            'n_download',
            'output_tgz_root'
        ]
    )
    download_wf.inputs.input_s3_links = args.input_s3_links.str
    download_wf.inputs.fasttrack_package_id = args.package_id
    download_wf.inputs.n_download = args.n_download
    download_wf.inputs.output_tgz_root = f'{args.output_dir}/TGZ'

    download_wf.add(
        pydra.ShellCommandTask(
            name='setup_tgz_dir',
            executable='mkdir',
            args=f'-p {download_wf.inputs.output_tgz_root}'.split(' ')
        )
    )

    download_wf.add(
        pydra.ShellCommandTask(
            name='download',
            executable='downloadcmd',
            args=f'-dp {download_wf.inputs.fasttrack_package_id} -t {download_wf.inputs.input_s3_links} -d {download_wf.inputs.output_tgz_root} --workerThreads {download_wf.inputs.n_download}'.split(' ')
        )
    )

    download_wf.add(
        collect_glob(
            name='collect_tgzs',
            pattern=f'{download_wf.inputs.output_tgz_root}/*.tgz',
            mode='files'
        )
    )

    download_wf.set_output(
        [
            ('output_tgzs', download_wf.collect_tgzs.lzout.out)
        ]
    )


    # Create the TGZ unpacking workflow
    unpack_wf = pydra.Workflow(
        name="tgz2dicom",
        input_spec=[
            'input_tgzs',
            'output_dicom_root'
        ]
    )
    unpack_wf.inputs.input_tgzs = download_wf.lzout.output_tgzs
    # unpack_wf.inputs.input_tgzs = collect_glob(pattern=f'{args.output_dir}/DICOM/sub-*/ses-*', mode='directories')
    unpack_wf.inputs.output_dicom_root = f'{args.output_dir}/DICOM'

    unpack_wf.add(
        pydra.ShellCommandTask(
            name='setup_dicom_dir',
            executable='mkdir',
            args=f'-p {unpack_wf.inputs.output_dicom_root}'.split(' ')
        )
    )

    unpack_wf.split('input_tgzs', input_tgzs=unpack_wf.inputs.input_tgzs)
    unpack_wf.add(
        pydra.ShellCommandTask(
            name='unpack',
            executable='tar',
            args=f'-xzf {unpack_wf.inputs.input_tgzs} -C {unpack_wf.inputs.output_dicom_root}'.split(' ')
        )
    )

    unpack_wf.add(
        collect_glob(
            name='collect_bids_sessions',
            pattern=f'{unpack_wf.inputs.output_dicom_root}/sub-*/ses-*',
            mode='directories'
        )
    )

    unpack_wf.set_output(
        [
            ('output_bids_sessions', unpack_wf.collect_bids_sessions.lzout.out)
        ]
    )

    # Create the DICOM to BIDS conversion workflow
    dcm2bids_wf = pydra.Workflow(
        name="dicom2bids",
        input_spec=[
            'input_sessions_list',
            'input_dicom_root',
            'dcm2bids_config_json',
            'output_bids_root'
        ]
    )
    dcm2bids_wf.inputs.input_dicom_root = unpack_wf.inputs.output_dicom_root
    dcm2bids_wf.inputs.dcm2bids_config_json = args.input_dcm2bids_config.str
    dcm2bids_wf.inputs.output_bids_root = f'{args.output_dir}/BIDS'

    dcm2bids_wf.add(
        pydra.ShellCommandTask(
            name='setup_bids_dir',
            executable='mkdir',
            args=f'-p {dcm2bids_wf.inputs.output_bids_root}'.split(' ')
        )
    )

    dcm2bids_wf.split('input_sessions_list', input_sessions_list=unpack_wf.lzout.output_bids_sessions)
    dcm2bids_wf.add(
        format_dcm2bids_args(
            bids_session_directory=unpack_wf.lzout.output_bids_sessions,
            config_file=dcm2bids_wf.inputs.dcm2bids_config_json,
            output_dir=dcm2bids_wf.inputs.output_bids_root
        )
    )

    dcm2bids_wf.add(
        pydra.ShellCommandTask(
            name='dcm2bids',
            executable='dcm2bids',
            args=dcm2bids_wf.format_dcm2bids_args.lzout.out
        )
    )

    # My pydra fasttrack2bids workflow

    # download
    with pydra.Submitter(plugin='cf', n_procs=args.n_download) as submitter:
        submitter(download_wf)

    download_results = download_wf.result()
    print(download_results)

    # unpack
    with pydra.Submitter(plugin='cf', n_procs=args.n_unpack) as submitter:
        submitter(unpack_wf)

    unpack_results = unpack_wf.result()
    print(unpack_results)

    # dicom2bids
    with pydra.Submitter(plugin='cf', n_procs=args.n_dcm2bids) as submitter:
        submitter(dcm2bids_wf)

    dcm2bids_results = dcm2bids_wf.result()
    print(dcm2bids_results)


if __name__ == '__main__':
    main()

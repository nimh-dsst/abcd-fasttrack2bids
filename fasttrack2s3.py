#! /usr/bin/env python3


# pseudocode
#
# @TODO: Add additonal option to save out logs to a specific file
# @TODO: Add option to filter by either inclusion or exclusion of the ftq_* columns
#    e.g. "{"ftq_complete": "0"}""
# 1. Parse command line arguments
# @TODO: Add levels of log messages of warning/caution for the user to know what's going on with datatypes specifically
# 2. Warn users about the filtered qc_input file for invalid data. Things like:
#    - fMRI is selected and there's no fieldmap with it
# (NEVERMIND) @TODO: Add more search filter options using BIDS participants.tsv
# 3. Apply pid, sid, and datatype filters to filter the qc_input file
# @TODO: Add option to only output S3 links and skip producing the filtered qc_input file
# 4. Produce both the filtered qc_input and the s3_output files suffixed with
#    filtered_{datatypes}_p-{participant_count}_s-{session_count}, examples like:
#    - filtered_all_p-11807_s-19104
#    - filtered_all-anat_p-11807_s-19104
#    - filtered_all-task-rest_p-9732_s-16324
#    - filtered_all-task-rest+only-t1w-normalized_p-7216_s-12024
#


# imports
import argparse
import csv
import logging
import pandas
import re

from copy import deepcopy
from logging import debug, info, warning, error, critical
from pathlib import Path
from utilities import readable, writable


# constants
HERE = Path(__file__).parent

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

SESSIONS = [
    'ses-baselineYear1Arm1',
    'ses-2YearFollowUpYArm1',
    'ses-4YearFollowUpYArm1',
    'ses-6YearFollowUpYArm1',
    'ses-8YearFollowUpYArm1',
    'ses-10YearFollowUpYArm1'
]

DATATYPES = {
    "all": {
        "warning": 
            "The \"all\" datatype contains everything except QA data.",
        "types": [
            "_ABCD-DTI_",
            "_ABCD-Diffusion-FM_",
            "_ABCD-Diffusion-FM-AP_",
            "_ABCD-Diffusion-FM-PA_",
            "_ABCD-MID-fMRI_",
            "_ABCD-nBack-fMRI_",
            "_ABCD-rsfMRI_",
            "_ABCD-SST-fMRI_",
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_",
            "_ABCD-T1_",
            "_ABCD-T1-NORM_",
            "_ABCD-T2_",
            "_ABCD-T2-NORM_"
        ]
    },
    "all-anat": {
        "warning": 
            "The \"all-anat\" datatype contains both T1 and T2 as-acquired. Siemens scans also include T1 and T2 normalized.",
        "types": [
            "_ABCD-T1_",
            "_ABCD-T1-NORM_",
            "_ABCD-T2_",
            "_ABCD-T2-NORM_"
        ]
    },
    "all-t1w": {
        "warning": 
            "The \"all-t1w\" datatype contains T1 as-acquired. Siemens scans also include T1 normalized.",
        "types": [
            "_ABCD-T1_",
            "_ABCD-T1-NORM_"
        ],
    },
    "all-t2w": {
        "warning": 
            "The \"all-t2w\" datatype contains T2 as-acquired. Siemens scans also include T2 normalized.",
        "types": [
            "_ABCD-T2_",
            "_ABCD-T2-NORM_"
        ],
    },
    "all-dwi": {
        "warning": 
            "The \"all-dwi\" datatype contains both DWI scans and DWI field maps.",
        "types": [
            "_ABCD-DTI_",
            "_ABCD-Diffusion-FM_",
            "_ABCD-Diffusion-FM-AP_",
            "_ABCD-Diffusion-FM-PA_"
        ],
    },
    "all-fmap": {
        "warning": 
            "The \"all-fmap\" datatype contains both DWI field maps and fMRI field maps.",
        "types": [
            "_ABCD-Diffusion-FM_",
            "_ABCD-Diffusion-FM-AP_",
            "_ABCD-Diffusion-FM-PA_",
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_"
        ],
    },
    "all-func": {
        "warning": 
            "The \"all-func\" datatype contains all task-based and resting-state fMRI as well as all fMRI field maps.",
        "types": [
            "_ABCD-MID-fMRI_",
            "_ABCD-nBack-fMRI_",
            "_ABCD-rsfMRI_",
            "_ABCD-SST-fMRI_",
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_"
        ],
    },
    "all-task-MID": {
        "warning": 
            "The \"all-task-MID\" datatype contains all MID task fMRI as well as all fMRI field maps.",
        "types": [
            "_ABCD-MID-fMRI_",
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_"
        ],
    },
    "all-task-nback": {
        "warning": 
            "The \"\" datatype contains all nback task fMRI as well as all fMRI field maps.",
        "types": [
            "_ABCD-nBack-fMRI_",
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_"
        ],
    },
    "all-task-rest": {
        "warning": 
            "The \"\" datatype contains all resting-state fMRI as well as all fMRI field maps.",
        "types": [
            "_ABCD-rsfMRI_",
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_"
        ],
    },
    "all-task-SST": {
        "warning": 
            "The \"\" datatype contains all SST task fMRI as well as all fMRI field maps.",
        "types": [
            "_ABCD-SST-fMRI_",
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_"
        ],
    },
    "all-qa": {
        "warning": 
            "The \"all-qa\" datatype contains all QA scans. This behaves the same as the \"only-qa\" datatype.",
        "types": [
            "QA_"
        ],
    },
    "only-dwi": {
        "warning": 
            "The \"only-dwi\" datatype contains only .",
        "types": [
            "_ABCD-DTI_"
        ],
    },
    "only-fmap-dwi": {
        "warning": 
            "The \"only-fmap-dwi\" datatype contains only .",
        "types": [
            "_ABCD-Diffusion-FM_",
            "_ABCD-Diffusion-FM-AP_",
            "_ABCD-Diffusion-FM-PA_"
        ],
    },
    "only-fmap-func": {
        "warning": 
            "The \"only-fmap-func\" datatype contains only .",
        "types": [
            "_ABCD-fMRI-FM_",
            "_ABCD-fMRI-FM-AP_",
            "_ABCD-fMRI-FM-PA_"
        ],
    },
    "only-func": {
        "warning": 
            "The \"only-func\" datatype contains only .",
        "types": [
            "_ABCD-MID-fMRI_",
            "_ABCD-nBack-fMRI_",
            "_ABCD-rsfMRI_",
            "_ABCD-SST-fMRI_"
        ],
    },
    "only-task-MID": {
        "warning": 
            "The \"only-task-\" datatype contains only .",
        "types": [
            "_ABCD-MID-fMRI_"
        ],
    },
    "only-task-nback": {
        "warning": 
            "The \"only-task-nback\" datatype contains only .",
        "types": [
            "_ABCD-nBack-fMRI_"
        ],
    },
    "only-task-rest": {
        "warning": 
            "The \"only-task-rest\" datatype contains only .",
        "types": [
            "_ABCD-rsfMRI_"
        ],
    },
    "only-task-SST": {
        "warning": 
            "The \"only-task-SST\" datatype contains only .",
        "types": [
            "_ABCD-SST-fMRI_"
        ],
    },
    "only-t1w-asacquired": {
        "warning": 
            "The \"only-t1w-asacquired\" datatype contains only .",
        "types": [
            "_ABCD-T1_"
        ],
    },
    "only-t1w-normalized": {
        "warning": 
            "The \"only-t1w-normalized\" datatype contains only .",
        "types": [
            "_ABCD-T1-NORM_"
        ],
    },
    "only-t2w-asacquired": {
        "warning": 
            "The \"only-t2w-asacquired\" datatype contains only .",
        "types": [
            "_ABCD-T2_"
        ],
    },
    "only-t2w-normalized": {
        "warning": 
            "The \"only-t2w-normalized\" datatype contains only .",
        "types": [
            "_ABCD-T2-NORM_"
        ],
    },
    "only-qa": {
        "warning": 
            "The \"only-qa\" datatype contains only QA scans. This behaves the same as the \"all-qa\" datatype.",
        "types": [
            "QA_"
        ]
    },
}

# create help strings for the argparse options
log_levels_str = "\n    ".join(LOG_LEVELS)
sessions_str = "\n    ".join(SESSIONS)
datatypes_str = "\n    ".join( list(DATATYPES.keys()) )


# functions
def cli():
    # build parser CLI
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=f"Filter down NDA ABCD fast track series TGZ files from "
                    "an abcd_fastqc01.txt file using datatype, participant ID, "
                    "and session ID options.")


    # positional arguments
    parser.add_argument(dest='qc_input', metavar='INPUT_FILE', type=readable,
                        help="The NDA-formatted abcd_fastqc01.txt as-provided "
                            "from the NDA.")

    parser.add_argument(dest='output_dir', metavar='OUTPUT_DIR', type=writable,
                        help="The output folder for the S3 links file and "
                            "subset abcd_fastqc01.txt file.")


    # make argument groups
    part_sess = parser.add_argument_group(
        title='Participant and Session Options',
        description="You can filter by exact participants and sessions with "
                    "the below options. All participant IDs can be in "
                    "either NDA GUID or BIDS ID or just the last eight ID "
                    "characters format. Letter case is ignored during "
                    "filtering. In the absence of any participant or session "
                    "options, all participants and sessions are included.")

    participants = part_sess.add_mutually_exclusive_group()
    sessions = part_sess.add_mutually_exclusive_group()

    control = parser.add_argument_group(title='Control Options')


    # controls argument group
    control.add_argument('-d', '--datatypes', nargs='+', default=['all'],
                        choices=['all'] + list(DATATYPES.keys()), metavar='TYPE',
                        help="The space-separated datatypes to include. Defaults to \"all\".\n"
                            "Options are:\n"
                            f"    {datatypes_str}")

    # control.add_argument('-x', '--exclude', nargs='+', type=str, default=[],
    #                     help="Space-separated strings to exclude within"
    #                         "ftq_series_id. Defaults to no exclusions.")

    control.add_argument('-sep', '--separate', action='store_true', default=False,
                        help="Separate the output file by session. Defaults "
                            "to False.")

    control.add_argument('-l', '--log-level', metavar='LEVEL',
                        choices=LOG_LEVELS, default='INFO',
                        help="Set the minimum logging level. Defaults to INFO.\n"
                            "Options, in most to least verbose order, are:\n"
                            f"    {log_levels_str}")


    # participant and session argument group
    part_sess.add_argument('-csv', '--csv', '--participant-session-csv',
                            default=None, metavar='FILE',type=readable,
                            help="The path to a comma-separated value file with "
                                "no header or index column. The file MUST have "
                                "exactly 1 participant ID, a comma, and then 1 "
                                "session ID per line. This is the preferred "
                                "method of passing in exact pairings of "
                                "participants and sessions to convert.")

    participants.add_argument('-pid', '--participant-id', nargs='+',
                                default=None, metavar='PID', type=str,
                                help="A space-separated exact participant ID "
                                    "list to filter on. Mutually exclusive "
                                    "with -ptxt.")

    participants.add_argument('-ptxt', '--participant-txt',
                                default=None, metavar='FILE', type=readable,
                                help="The path to a newline-separated plain "
                                    "text file with exactly 1 participant ID "
                                    "per line. Mutually exclusive with -pid.")

    sessions.add_argument('-sid', '--session-id', nargs='+', metavar='SID',
                            choices=SESSIONS,
                            default=SESSIONS,
                            help="A space-separated session ID list to filter "
                                "on. Defaults to all sessions. Mutually "
                                "exclusive with -stxt.\n"
                                "Options are:\n"
                                f"    {sessions_str}")

    sessions.add_argument('-stxt', '--session-txt', metavar='FILE',
                            default=None,  type=readable,
                            help="The path to a newline-separated plain text "
                                "file with exactly 1 session ID per line. "
                                "Mutually exclusive with -sid.")


    return parser.parse_args()


def main():
    # 1. Parse command line arguments
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

    debug(args)

    # read in the participant and session csv file
    subses_list = []
    subjects = []
    sessions = []

    if args.csv != None:
        # read in the pid/sid csv file
        with open(args.csv, 'r') as f:
            for line in f.readlines():
                split = line.rstrip('\n').strip().split(',')

                if len(split) != 2:
                    raise ValueError(f"Invalid CSV format in {args.csv}")
                else:
                    subses_list.append(split)

    else:
        # read in the pid txt file
        if args.participant_txt != None:
            with open(args.participant_txt, 'r') as f:
                for line in f.readlines():
                    subjects.append(line.rstrip('\n').strip())

        elif args.participant_id != None:
            for pid in args.participant_id:
                subjects.append(pid)

        else:
            warning("No participant IDs provided. All participants will be included.")

        # read in the sid txt file
        if args.session_txt != None:
            with open(args.session_txt, 'r') as f:
                for line in f.readlines():
                    sessions.append(line.rstrip('\n').strip())

        else:
            sessions = args.session_id

    debug(subses_list)
    debug(subjects)
    debug(sessions)

    # sanitize the subject and session search strings
    subses = []

    if len(subses_list) > 0:
        for sub, ses in subses_list:
            if len(sub) < 8:
                raise ValueError(f"Invalid participant ID: {sub}")

            subses.append(sub.upper()[-8:] + '_' + ses.lstrip('ses-'))

    if len(subjects) > 0:
        for sub in subjects:
            if len(sub) < 8:
                raise ValueError(f"Invalid participant ID: {sub}")

        subjects = [sub.upper()[-8:] for sub in subjects]

    if len(sessions) > 0:
        for ses in sessions:
            if ses not in SESSIONS:
                raise ValueError(f"Invalid session ID: {ses}")

        sessions = [ses.lstrip('ses-') for ses in sessions]

    if len(subses) == 0 and len(subjects) == 0 and len(sessions) == 0:
        warning("No participant or session filters provided. All participants and sessions will be included.")
        

    # collect all datatypes
    datatypes_str = "+".join(sorted(args.datatypes))
    dt_set = set()
    for datatype in args.datatypes:
        for t in set(DATATYPES[datatype]['types']):
            dt_set.add(t)

    dt_list = sorted(list(dt_set))

    debug(datatypes_str)
    debug(dt_list)

    # 2. Warn users about the filtered qc_input file for invalid data. Things like:
    #    - fMRI is selected and there's no fieldmap with it

    # 3. Apply pid, sid, and datatype filters to filter the qc_input file

    # Read in the qc_input file
    input = pandas.read_csv(args.qc_input, sep='\t', dtype=str)

    # Get the first row for later before it's gone
    row0 = input.iloc[0]

    # Filter by subses
    if len(subses) != 0:
        mask = input['ftq_series_id'].str.contains('|'.join(subses), flags=re.IGNORECASE)
        input = input[mask]

    # Filter by subjects
    if len(subjects) != 0:
        mask = input['ftq_series_id'].str.contains('|'.join(subjects), flags=re.IGNORECASE)
        input = input[mask]

    # Filter by sessions
    if len(sessions) != 0:
        mask = input['ftq_series_id'].str.contains('|'.join(sessions), flags=re.IGNORECASE)
        input = input[mask]

    # Filter by datatype
    input = input[input['ftq_series_id'].str.contains('|'.join(dt_list))]

    debug(input["ftq_series_id"])

    # 4. Produce both the filtered qc_input file and the s3_output file named as
    #    {qc_input}_{suffix}.txt, see format at the top of this file
    unique_sub = list(set([series.split('_')[0] for series in input['ftq_series_id']]))
    unique_subses = list(set([(series.split('_')[0], series.split('_')[1]) for series in input['ftq_series_id']]))
    suffix = f"{datatypes_str}_p-{len(unique_sub)}_s-{len(unique_subses)}"

    debug(suffix)

    # check if the separate flag is being flown
    if args.separate:
        output_dir = Path(f"{args.output_dir}/{args.qc_input.stem}_{suffix}")
        output_dir.mkdir(exist_ok=True)
    else:
        output_dir = args.output_dir

    # write out the S3 links file
    output_s3 = args.output_dir / f"{args.qc_input.stem}_{suffix}_s3links.txt"

    with open(output_s3, 'w') as f:
        for series in input['file_source']:
            f.write(f"{series}\n")

    # write out the filtered qc_input file
    output_qc = args.output_dir / f"{args.qc_input.stem}_{suffix}_filtered.txt"

    # append back in the row 0 for completeness
    input.loc[-1] = row0
    input.index = input.index + 1  # shift index
    input = input.sort_index()  # sort by index
    input.to_csv(output_qc, sep='\t', quoting=csv.QUOTE_ALL, index=False)

    if args.separate:
        # for every subject+session pair
        for subber, sesser in unique_subses:
            # write out a "mini" S3 links file
            output_mini_s3 = output_dir / f"sub-{subber}_ses-{sesser}_s3links.txt"

            mask = input['ftq_series_id'].str.contains(f"{subber}_{sesser}", flags=re.IGNORECASE)
            subses_output = deepcopy(input[mask])

            with open(output_mini_s3, 'w') as f:
                for series in subses_output['file_source']:
                    f.write(f"{series}\n")

            # write out a "mini" qc_input file
            output_mini_qc = output_dir / f"sub-{subber}_ses-{sesser}_filtered.txt"

            # append back in the row 0 for completeness
            subses_output.loc[-1] = row0
            subses_output.index = subses_output.index + 1
            subses_output = subses_output.sort_index()
            subses_output.to_csv(output_mini_qc, sep='\t', quoting=csv.QUOTE_ALL, index=False)
            del(subses_output)

if __name__ == '__main__':
    main()

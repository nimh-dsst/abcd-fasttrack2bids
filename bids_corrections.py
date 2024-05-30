#! /usr/bin/env python3

# The purpose of this script is to correct BIDS data in the outputs

# Importing the required libraries
import argparse
import logging
import os

from bids import BIDSLayout
from dependencies.sefm_eval_and_json_editor import insert_edit_json
from dependencies.sefm_eval_and_json_editor import read_bids_layout
from dependencies.sefm_eval_and_json_editor import sefm_select
from dependencies.sefm_eval_and_json_editor import seperate_concatenated_fm
from logging import debug, info, warning, error, critical
from pathlib import Path
from utilities import readable, writable, available

# default logging basic configuration
logging.basicConfig(level=logging.INFO)

def cli():
    parser = argparse.ArgumentParser(description='Correct BIDS data')

    # very necessary arguments
    parser.add_argument('-b', '--bids', type=writable, required=True,
                        help='Path to the BIDS input directory')
    parser.add_argument('-t', '--temporary', type=available, required=True,
                        help='Path to the temporary directory for intermediary files')
    parser.add_argument('-l', '--logs', type=available, required=True,
                        help='Directory path in which to put log files')

    # optional arguments
    parser.add_argument('--SeparateFieldMaps', action='store_true', required=False,
                        help='Separate all concatenated field maps using the '
                            'DCAN-Labs/abcd-dicom2bids seperate_concatenated_fm function. '
                            'WARNING: Requires FSL as a dependency.')

    parser.add_argument('--funcfmapIntendedFor', nargs=1, default=None, required=False,
                        metavar='MRE_DIR',
                        help='Assign IntendedFor fields to functional fmaps using the '
                            'DCAN-Labs/abcd-dicom2bids eta^2 technique. '
                            'This argument also triggers the --SeparateFieldMaps option. '
                            'WARNING: Requires FSL and MATLAB Runtime Environment as dependencies.')

    parser.add_argument('--dwifmapIntendedFor', action='store_true', required=False,
                        help='Assign IntendedFor fields to functional fmaps using the '
                            'DCAN-Labs/abcd-dicom2bids eta^2 technique. '
                            'This argument also triggers the --SeparateFieldMaps option. '
                            'WARNING: Requires FSL and MATLAB Runtime Environment as dependencies.')

    parser.add_argument('--fmapEffectiveEchoSpacing', action='store_true', required=False,
                        help='Inject the EffectiveEchoSpacing field into the '
                            'fmap JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--funcEffectiveEchoSpacing', action='store_true', required=False,
                        help='Inject the EffectiveEchoSpacing field into the '
                            'func JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--PhaseEncoding', action='store_true', required=False,
                        help='Make sure both the PhaseEncodingDirection and '
                            'PhaseEncodingAxis fields are present in the '
                            'func JSON sidecar metadata files, '
                            'as recommended by DCAN-Labs/abcd-dicom2bids.')

    parser.add_argument('--DCAN', action='store_true', required=False,
                        help='Run all of the DCAN-Labs/abcd-dicom2bids recommendations. '
                            'WARNING: Requires FSL and MATLAB Runtime Environment as dependencies.')

    return parser.parse_args()


def fsl_check():
    # Set FSLDIR environment variable
    if 'FSLDIR' not in os.environ and 'FSL_DIR' not in os.environ:
        raise Exception("Neither FSLDIR nor FSL_DIR environment variables are set. Unable to use as-is.")
    elif 'FSLDIR' not in os.environ:
        os.environ['FSLDIR'] = os.environ['FSL_DIR']
    elif 'FSL_DIR' not in os.environ:
        os.environ['FSL_DIR'] = os.environ['FSLDIR']

    # for this function's usage of FSLDIR
    fsl_dir = os.environ['FSLDIR'] + '/bin'

    return fsl_dir


# Most of the following functions are based on the sefm_eval_and_json_editor.py main function


def separate_fmaps(layout, subsess, args):
    fsl_dir = fsl_check()

    for subject, sessions in subsess:

        # Check if there are any concatenated field maps
        fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func', direction='both')

        if fmaps:
            info(f"Func fieldmaps for {subject}, {sessions} are concatenated. Running seperate_concatenated_fm.")
            seperate_concatenated_fm(layout, subject, sessions, fsl_dir)

            # recreate layout with the additional fmaps
            layout = BIDSLayout(args.bids)

    return layout


def assign_funcfmapIntendedFor(layout, subsess, args):
    layout = separate_fmaps(layout, subsess, args)

    fsl_dir = fsl_check()

    for subject, sessions in subsess:

        # Check if there are func fieldmaps and return a list of each SEFM pos/neg pair
        fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func')        

        if fmaps:
            info(f"Running SEFM select for {subject}, {sessions}")
            base_temp_dir = fmaps[0].dirname
            best_pos, best_neg = sefm_select(layout, subject, sessions, base_temp_dir, fsl_dir, args.funcfmapIntendedFor[0], debug=False)

    return BIDSLayout(args.bids)


def inject_fmapEffectiveEchoSpacing(layout, subsess, args):
    for subject, sessions in subsess:

        fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func')        

        if fmap:
            for sefm in [os.path.join(x.dirname, x.filename) for x in fmap]:
                sefm_json = sefm.replace('.nii.gz', '.json')
                sefm_metadata = layout.get_metadata(sefm)

                if 'Philips' in sefm_metadata['Manufacturer']:
                    insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.00062771)
                if 'GE' in sefm_metadata['Manufacturer']:
                    insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.000536)
                if 'Siemens' in sefm_metadata['Manufacturer']:
                    insert_edit_json(sefm_json, 'EffectiveEchoSpacing', 0.000510012)
    
    return BIDSLayout(args.bids)


def inject_funcEffectiveEchoSpacing(layout, subsess, args):
    for subject, sessions in subsess:

        func = layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')

        if func:
            for task in [os.path.join(x.dirname, x.filename) for x in func]:
                task_json = task.replace('.nii.gz', '.json')
                task_metadata = layout.get_metadata(task)

                if 'Philips' in task_metadata['Manufacturer']:
                    insert_edit_json(task_json, 'EffectiveEchoSpacing', 0.00062771)
                if 'GE' in task_metadata['Manufacturer']:
                    if 'DV26' in task_metadata['SoftwareVersions']:
                        insert_edit_json(task_json, 'EffectiveEchoSpacing', 0.000556)
                if 'Siemens' in task_metadata['Manufacturer']:
                    insert_edit_json(task_json, 'EffectiveEchoSpacing', 0.000510012)
    
    return BIDSLayout(args.bids)


def add_PhaseEncodingAxisAndDirection(layout, subsess, args):
    for subject, sessions in subsess:

        # PE direction vs axis
        func = layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')

        if func:
            for task in [os.path.join(x.dirname, x.filename) for x in func]:
                task_json = task.replace('.nii.gz', '.json')
                task_metadata = layout.get_metadata(task)

                # add whichever field is missing based on the other
                if "PhaseEncodingAxis" in task_metadata:
                    insert_edit_json(task_json, 'PhaseEncodingDirection', task_metadata['PhaseEncodingAxis'])
                elif "PhaseEncodingDirection" in task_metadata:
                    insert_edit_json(task_json, 'PhaseEncodingAxis', task_metadata['PhaseEncodingDirection'].strip('-'))

    return BIDSLayout(args.bids)


def main():
    args = cli()

    # Load the bids layout
    layout = BIDSLayout(args.bids)
    subsess = read_bids_layout(layout, subject_list=layout.get_subjects(), collect_on_subject=True)

    # check if the concatenated field maps separation argument was passed
    if args.SeparateFieldMaps:
        info("Separating concatenated field maps")
        layout = separate_fmaps(layout, subsess, args)

    # check if the acq-func fmap IntendedFor argument was provided
    if args.funcfmapIntendedFor != None:
        info("Assigning func fmap IntendedFor fields")
        layout = assign_funcfmapIntendedFor(layout, subsess, args)

    # check if the acq-dwi fmap IntendedFor argument was provided
    if args.dwifmapIntendedFor:
        critical("Assigning dwi fmap IntendedFor fields is not yet implemented")

    # check if the fmap EffectiveEchoSpacing argument was provided
    if args.fmapEffectiveEchoSpacing:
        info("Injecting fmap EffectiveEchoSpacing fields")
        layout = inject_fmapEffectiveEchoSpacing(layout, subsess, args)

    # check if the func EffectiveEchoSpacing argument was provided
    if args.funcEffectiveEchoSpacing:
        info("Injecting func EffectiveEchoSpacing fields")
        layout = inject_funcEffectiveEchoSpacing(layout, subsess, args)

    # check if the PhaseEncoding argument was provided
    if args.PhaseEncoding:
        info("Adding PhaseEncodingAxis and Direction fields")
        layout = add_PhaseEncodingAxisAndDirection(layout, subsess, args)

    # check if the DCAN argument was provided
    if args.DCAN:
        info("Running all DCAN-Labs/abcd-dicom2bids recommendations")
        layout = separate_fmaps(layout, subsess, args)
        layout = assign_funcfmapIntendedFor(layout, subsess, args)
        # @TODO layout = assign_dwifmapIntendedFor(layout, subsess, args) 
        layout = inject_fmapEffectiveEchoSpacing(layout, subsess, args)
        layout = inject_funcEffectiveEchoSpacing(layout, subsess, args)
        layout = add_PhaseEncodingAxisAndDirection(layout, subsess, args)


if __name__ == '__main__':
    main()

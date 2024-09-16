#! /usr/bin/env python3

# The purpose of this script is to correct BIDS data in the outputs

# Importing the required libraries
import argparse
import json
import logging
import os
import pandas
import re
import shutil

from bids import BIDSLayout
from copy import deepcopy
from dependencies.sefm_eval_and_json_editor import insert_edit_json
from dependencies.sefm_eval_and_json_editor import read_bids_layout
from dependencies.sefm_eval_and_json_editor import sefm_select
from dependencies.sefm_eval_and_json_editor import seperate_concatenated_fm
from logging import debug, info, warning, error, critical
from pathlib import Path
from utilities import readable, writable, available

# get the path to here
HERE = Path(__file__).parent.resolve()
dwi_tables = HERE / 'dependencies/ABCD_Release_2.0_Diffusion_Tables'
ds_desc = HERE / 'dependencies/bids/dataset_description.json'

# Set up logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

# create help strings for the log level option
log_levels_str = "\n    ".join(LOG_LEVELS)


def cli():
    parser = argparse.ArgumentParser(description='Correct BIDS data')

    # very necessary arguments
    parser.add_argument('-b', '--bids', type=writable, required=True,
                        help='Path to the BIDS input directory')
    parser.add_argument('-t', '--temporary', type=writable, required=True,
                        help='Path to the temporary directory for intermediary files')

    # optional arguments
    parser.add_argument('-l', '--log-level', metavar='LEVEL',
                        choices=LOG_LEVELS, default='INFO',
                        help="Set the minimum logging level. Defaults to INFO.\n"
                            "Options, in most to least verbose order, are:\n"
                            f"    {log_levels_str}")
    parser.add_argument('--dwiCorrectOldGE', action='store_true', required=False,
                        help='Correct any present "old" GE DV25 through DV28 '
                            'DWI BVAL and BVEC files.')

    parser.add_argument('--fmapSeparate', action='store_true', required=False,
                        help='Separate all concatenated field maps using the '
                            'DCAN-Labs/abcd-dicom2bids seperate_concatenated_fm function. '
                            'WARNING: Requires FSL as a dependency.')

    parser.add_argument('--dwifmapIntendedFor', action='store_true', required=False,
                        help='Assign IntendedFor fields to diffusion fmaps using the '
                            'DCAN-Labs/abcd-dicom2bids eta^2 technique.')

    parser.add_argument('--funcfmapIntendedFor', nargs=1, default=None, required=False,
                        metavar='MRE_DIR',
                        help='Assign IntendedFor fields to functional fmaps using the '
                            'DCAN-Labs/abcd-dicom2bids eta^2 technique. '
                            'This argument also triggers the --fmapSeparate option. '
                            'WARNING: Requires FSL and MATLAB Runtime Environment 9.1 as dependencies.')

    parser.add_argument('--fmapCorrectIntendedFor', action='store_true', required=False,
                        help='Correct any present IntendedFor fields in field map '
                            'JSON sidecar metadata files by inserting the BIDS URI '
                            'where it is not present or removing empty IntendedFor lists.')

    parser.add_argument('--anatDwellTime', action='store_true', required=False,
                        help='Inject the DwellTime field into the '
                            'anat JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--dwiTotalReadoutTime', action='store_true', required=False,
                        help='Inject the TotalReadoutTime field into the '
                            'dwi and dwi fmap JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--dwiEffectiveEchoSpacing', action='store_true', required=False,
                        help='Inject the EffectiveEchoSpacing field into the '
                            'dwi and dwi fmap JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--funcfmapEffectiveEchoSpacing', action='store_true', required=False,
                        help='Inject the EffectiveEchoSpacing field into the '
                            'func fmap JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--funcEffectiveEchoSpacing', action='store_true', required=False,
                        help='Inject the EffectiveEchoSpacing field into the '
                            'func JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--dwifmapPhaseEncodingDirection', action='store_true', required=False,
                        help='Inject the PhaseEncodingDirection field into the '
                            'dwi fmap JSON sidecar metadata files, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--funcPhaseEncoding', action='store_true', required=False,
                        help='Make sure both the PhaseEncodingDirection and '
                            'PhaseEncodingAxis fields are present in the '
                            'func JSON sidecar metadata files, '
                            'as recommended by DCAN-Labs/abcd-dicom2bids.')

    parser.add_argument('--funcSliceTimingRemove', action='store_true', required=False,
                        help='Remove any present SliceTiming fields from '
                            'functional JSON sidecar metadata files, '
                            'as recommended by DCAN-Labs/abcd-dicom2bids.')

    parser.add_argument('--dwibvalCorrectFloatingPointError', action='store_true', required=False,
                        help='Correct any floating point errors in the DWI '
                            'BVAL files.')

    parser.add_argument('--fmapTotalReadoutTime', action='store_true', required=False,
                        help='Inject a calculated TotalReadoutTime field into the '
                            'fmap JSON sidecar metadata files if '
                            'EffectiveEchoSpacing and ReconMatrixPE are present, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--funcTotalReadoutTime', action='store_true', required=False,
                        help='Inject a calculated TotalReadoutTime field into the '
                            'func JSON sidecar metadata files if '
                            'EffectiveEchoSpacing and ReconMatrixPE are present, '
                            'as recommended by the DCAN-Labs/abcd-dicom2bids repo.')

    parser.add_argument('--fmapbvalbvecRemove', action='store_true', required=False,
                        help='Remove any present BVAL and BVEC files alongside '
                            'field maps.')

    parser.add_argument('--DCAN', nargs=1, default=None, required=False,
                        metavar='MRE_DIR',
                        help='Run all of the DCAN-Labs/abcd-dicom2bids recommendations. '
                            'WARNING: Requires FSL and MATLAB Runtime Environment 9.1 as dependencies.')

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


def df_append(df, data):
    df = pandas.concat([df, pandas.DataFrame(data, index=[0])], ignore_index=True)
    return df


def correct_old_GE_DV25_DV28(layout, subsess, args, df):
    for subject, sessions in subsess:

        # Check if there are any old GE DV25 through DV28 DWI BVAL and BVEC files
        dwi_niftis = layout.get(subject=subject, session=sessions, datatype='dwi', extension='.nii.gz')

        if dwi_niftis:
            for dwi_nifti in [os.path.join(x.dirname, x.filename) for x in dwi_niftis]:
                dwi_bval = dwi_nifti.replace('.nii.gz', '.bval')
                dwi_bvec = dwi_nifti.replace('.nii.gz', '.bvec')
                dwi_metadata = layout.get_metadata(dwi_nifti)

                if 'GE' in dwi_metadata['Manufacturer']:
                    for version in ['DV25', 'DV26', 'DV27', 'DV28', 'RX26', 'RX27', 'RX28']:
                        if version in dwi_metadata['SoftwareVersions']:
                            # correct the bval and bvec files
                            info(f'Overwriting the bval and bvec files for GE {version}: {dwi_nifti}')
                            if version == 'DV25':
                                shutil.copyfile(dwi_tables.joinpath('GE_bvals_DV25.txt'), dwi_bval)
                                df = df_append(df, {
                                    'time': pandas.Timestamp.now(),
                                    'function': 'correct_old_GE_DV25_DV28',
                                    'file': os.path.basename(dwi_bval),
                                    'field': 'n/a',
                                    'original_value': 'n/a',
                                    'corrected_value': 'GE_bvals_DV25.txt'
                                })
                                shutil.copyfile(dwi_tables.joinpath('GE_bvecs_DV25.txt'), dwi_bvec)
                                df = df_append(df, {
                                    'time': pandas.Timestamp.now(),
                                    'function': 'correct_old_GE_DV25_DV28',
                                    'file': os.path.basename(dwi_bvec),
                                    'field': 'n/a',
                                    'original_value': 'n/a',
                                    'corrected_value': 'GE_bvecs_DV25.txt'
                                })
                            else:
                                shutil.copyfile(dwi_tables.joinpath('GE_bvals_DV26.txt'), dwi_bval)
                                df = df_append(df, {
                                    'time': pandas.Timestamp.now(),
                                    'function': 'correct_old_GE_DV25_DV28',
                                    'file': os.path.basename(dwi_bval),
                                    'field': 'n/a',
                                    'original_value': 'n/a',
                                    'corrected_value': 'GE_bvals_DV26.txt'
                                })
                                shutil.copyfile(dwi_tables.joinpath('GE_bvecs_DV26.txt'), dwi_bvec)
                                df = df_append(df, {
                                    'time': pandas.Timestamp.now(),
                                    'function': 'correct_old_GE_DV25_DV28',
                                    'file': os.path.basename(dwi_bvec),
                                    'field': 'n/a',
                                    'original_value': 'n/a',
                                    'corrected_value': 'GE_bvecs_DV26.txt'
                                })

    return BIDSLayout(args.bids), df


def correct_IntendedFor(layout, subsess, args, df):
    for subject, sessions in subsess:

        # Check if there are any IntendedFor fields in the JSONs
        fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz')

        if fmaps:
            for fmap in [os.path.join(x.dirname, x.filename) for x in fmaps]:
                fmap_json = fmap.replace('.nii.gz', '.json')
                fmap_metadata = layout.get_metadata(fmap)

                if 'IntendedFor' in fmap_metadata:
                    # load in the JSON file
                    with open(fmap_json, 'r') as f:
                        contents = json.load(f)

                    original_value = contents['IntendedFor']

                    # if it's an empty list
                    if original_value == []:
                        # remove the empty IntendedFor field
                        del contents['IntendedFor']

                        # write the JSON file back out
                        with open(fmap_json, 'w') as f:
                            json.dump(contents, f, indent=4)

                    # else if it's a list with entries
                    elif type(original_value) is list:
                        corrected_value = []
                        for entry in original_value:
                            corrected_value.append(re.sub(r'^.*(sub-.+/)', 'bids::\g<1>', entry))

                        insert_edit_json(fmap_json, 'IntendedFor', corrected_value)

                    # otherwise it's a string and we need to correct just the one entry
                    else:
                        corrected_value = re.sub(r'^.*(sub-.+/)', 'bids::\g<1>', original_value)
                        insert_edit_json(fmap_json, 'IntendedFor', corrected_value)

    return BIDSLayout(args.bids), df


# Most of the following functions are based on the DCAN-Labs/abcd-dicom2bids
# sefm_eval_and_json_editor.py or correct_jsons.py main functions

def separate_fmaps(layout, subsess, args, df):
    fsl_dir = fsl_check()

    for subject, sessions in subsess:

        # Check if there are any concatenated field maps
        fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func', direction='both')

        if fmaps:
            info(f"Func fieldmaps for {subject}, {sessions} are concatenated. Running seperate_concatenated_fm.")
            seperate_concatenated_fm(layout, subject, sessions, fsl_dir)

            for fmap_nifti in [os.path.join(x.dirname, x.filename) for x in fmaps]:
                fmap_json = fmap_nifti.replace('.nii.gz', '.json')

                # remove the old concatenated field maps
                os.remove(fmap_nifti)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'separate_fmaps',
                    'file': os.path.basename(fmap_nifti),
                    'field': 'n/a',
                    'original_value': 'n/a',
                    'corrected_value': 'REMOVED'
                })
                os.remove(fmap_json)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'separate_fmaps',
                    'file': os.path.basename(fmap_json),
                    'field': 'n/a',
                    'original_value': 'n/a',
                    'corrected_value': 'REMOVED'
                })

            # recreate layout with the additional fmaps
            layout = BIDSLayout(args.bids)

    return layout, df


def assign_funcfmapIntendedFor(layout, subsess, args, df):
    fsl_dir = fsl_check()
    if args.DCAN != None:
        MRE_DIR = args.DCAN[0]
    elif args.funcfmapIntendedFor != None:
        MRE_DIR = args.funcfmapIntendedFor[0]
    else:
        raise Exception("No MRE_DIR provided for func fmap IntendedFor assignment.")

    debug(MRE_DIR)

    for subject, sessions in subsess:

        # Check if there are func fieldmaps and return a list of each SEFM pos/neg pair
        fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func')

        if fmaps:
            info(f"Running SEFM select for {subject}, {sessions}")
            # base_temp_dir = fmaps[0].dirname
            base_temp_dir = args.temporary
            best_pos, best_neg = sefm_select(layout, subject, sessions, base_temp_dir, fsl_dir, MRE_DIR, debug=False)
            for best in [best_pos, best_neg]:
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'assign_funcfmapIntendedFor',
                    'file': os.path.basename(best),
                    'field': 'IntendedFor',
                    'original_value': 'n/a',
                    'corrected_value': 'ADDED'
                })

    return BIDSLayout(args.bids), df


def assign_dwifmapIntendedFor(layout, subsess, args, df):
    for subject, sessions in subsess:

        # grap the DWI NIfTIs and the AP dwi fmap JSON
        dwi_niftis = layout.get(subject=subject, session=sessions, datatype='dwi', suffix='dwi', extension='.nii.gz')
        APs = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='dwi', direction='AP', extension='.json')

        if dwi_niftis and APs:
            dwi_relpath = []
            for dwi_nifti in [os.path.join(x.dirname, x.filename) for x in dwi_niftis]:
                dwi_relpath += [os.path.relpath(dwi_nifti, str(args.bids))]

            # pick the first AP fmap to assign to all dwi scans
            sorted_APs = sorted([os.path.join(AP.dirname, AP.filename) for AP in APs])
            debug(sorted_APs)
            AP_json = sorted_APs[0]
            insert_edit_json(AP_json, 'IntendedFor', dwi_relpath)
            df = df_append(df, {
                'time': pandas.Timestamp.now(),
                'function': 'assign_dwifmapIntendedFor',
                'file': os.path.basename(AP_json),
                'field': 'IntendedFor',
                'original_value': 'n/a',
                'corrected_value': str(dwi_relpath)
            })

    return BIDSLayout(args.bids), df


def inject_anatDwellTime(layout, subsess, args, df):
    for subject, sessions in subsess:

        anat = layout.get(subject=subject, session=sessions, datatype='anat', extension='.nii.gz')

        if anat:
            for TX in [os.path.join(x.dirname, x.filename) for x in anat]:
                TX_json = TX.replace('.nii.gz', '.json') 
                TX_metadata = layout.get_metadata(TX)

                if 'GE' in TX_metadata['Manufacturer']:
                    corrected_value = 0.000536
                elif 'Philips' in TX_metadata['Manufacturer']:
                    corrected_value = 0.00062771
                elif 'Siemens' in TX_metadata['Manufacturer']:
                    corrected_value = 0.000510012
                else:
                    error(f"Manufacturer not recognized for {TX} in inject_anatDwellTime")
                    continue

                insert_edit_json(TX_json, 'DwellTime', corrected_value)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'inject_anatDwellTime',
                    'file': os.path.basename(TX_json),
                    'field': 'DwellTime',
                    'original_value': 'n/a',
                    'corrected_value': corrected_value
                })

    return BIDSLayout(args.bids), df


def inject_dwiTotalReadoutTime(layout, subsess, args, df):
    for subject, sessions in subsess:

        dwi = layout.get(subject=subject, session=sessions, datatype='dwi', suffix='dwi', extension='.nii.gz')
        fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='dwi')

        scans = []
        if fmap:
            scans += [os.path.join(x.dirname, x.filename) for x in fmap]
        if dwi:
            scans += [os.path.join(x.dirname, x.filename) for x in dwi]

        for scan in scans:
            scan_json = scan.replace('.nii.gz', '.json')
            scan_metadata = layout.get_metadata(scan)

            if 'GE' in scan_metadata['Manufacturer']:
                if 'DV25' in scan_metadata['SoftwareVersions']:
                    corrected_value = 0.104528
                elif 'DV26' in scan_metadata['SoftwareVersions']:
                    corrected_value = 0.106752
                else:
                    continue
            elif 'Philips' in scan_metadata['Manufacturer']:
                corrected_value = 0.08976
            elif 'Siemens' in scan_metadata['Manufacturer']:
                corrected_value = 0.0959097
            else:
                error(f"Manufacturer not recognized for {scan} in inject_dwiTotalReadoutTime")
                continue

            insert_edit_json(scan_json, 'TotalReadoutTime', corrected_value)
            df = df_append(df, {
                'time': pandas.Timestamp.now(),
                'function': 'inject_dwiTotalReadoutTime',
                'file': os.path.basename(scan_json),
                'field': 'TotalReadoutTime',
                'original_value': 'n/a',
                'corrected_value': corrected_value
            })

    return BIDSLayout(args.bids), df


def inject_dwiEffectiveEchoSpacing(layout, subsess, args, df):
    for subject, sessions in subsess:

        dwi = layout.get(subject=subject, session=sessions, datatype='dwi', suffix='dwi', extension='.nii.gz')
        fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='dwi')

        scans = []
        if fmap:
            scans += [os.path.join(x.dirname, x.filename) for x in fmap]
        if dwi:
            scans += [os.path.join(x.dirname, x.filename) for x in dwi]

        for scan in scans:
            scan_json = scan.replace('.nii.gz', '.json')
            scan_metadata = layout.get_metadata(scan)

            if 'GE' in scan_metadata['Manufacturer']:
                if 'DV25' in scan_metadata['SoftwareVersions']:
                    corrected_value = 0.000752
                elif 'DV26' in scan_metadata['SoftwareVersions']:
                    corrected_value = 0.000768
                else:
                    continue
            elif 'Philips' in scan_metadata['Manufacturer']:
                corrected_value = 0.00062771
            elif 'Siemens' in scan_metadata['Manufacturer']:
                corrected_value = 0.000689998
            else:
                error(f"Manufacturer not recognized for {scan} in inject_dwiEffectiveEchoSpacing")
                continue

            insert_edit_json(scan_json, 'EffectiveEchoSpacing', corrected_value)
            df = df_append(df, {
                'time': pandas.Timestamp.now(),
                'function': 'inject_dwiEffectiveEchoSpacing',
                'file': os.path.basename(scan_json),
                'field': 'EffectiveEchoSpacing',
                'original_value': 'n/a',
                'corrected_value': corrected_value
            })

    return BIDSLayout(args.bids), df


def inject_funcfmapEffectiveEchoSpacing(layout, subsess, args, df):
    for subject, sessions in subsess:

        fmap = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz', acquisition='func')

        if fmap:
            for fm in [os.path.join(x.dirname, x.filename) for x in fmap]:
                fm_json = fm.replace('.nii.gz', '.json')
                fm_metadata = layout.get_metadata(fm)

                if 'GE' in fm_metadata['Manufacturer']:
                    corrected_value = 0.000536
                elif 'Philips' in fm_metadata['Manufacturer']:
                    corrected_value = 0.00062771
                elif 'Siemens' in fm_metadata['Manufacturer']:
                    corrected_value = 0.000510012
                else:
                    error(f"Manufacturer not recognized for {fm} in inject_funcfmapEffectiveEchoSpacing")
                    continue

                insert_edit_json(fm_json, 'EffectiveEchoSpacing', corrected_value)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'inject_funcfmapEffectiveEchoSpacing',
                    'file': os.path.basename(fm_json),
                    'field': 'EffectiveEchoSpacing',
                    'original_value': 'n/a',
                    'corrected_value': corrected_value
                })

    return BIDSLayout(args.bids), df


def inject_funcEffectiveEchoSpacing(layout, subsess, args, df):
    for subject, sessions in subsess:

        func = layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')

        if func:
            for task in [os.path.join(x.dirname, x.filename) for x in func]:
                task_json = task.replace('.nii.gz', '.json')
                task_metadata = layout.get_metadata(task)

                if 'GE' in task_metadata['Manufacturer']:
                    if 'DV26' in task_metadata['SoftwareVersions']:
                        corrected_value = 0.000556
                    else:
                        continue
                elif 'Philips' in task_metadata['Manufacturer']:
                    corrected_value = 0.00062771
                elif 'Siemens' in task_metadata['Manufacturer']:
                    corrected_value = 0.000510012
                else:
                    error(f"Manufacturer not recognized for {task} in inject_funcEffectiveEchoSpacing")
                    continue

                insert_edit_json(task_json, 'EffectiveEchoSpacing', corrected_value)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'inject_funcEffectiveEchoSpacing',
                    'file': os.path.basename(task_json),
                    'field': 'EffectiveEchoSpacing',
                    'original_value': 'n/a',
                    'corrected_value': corrected_value
                })

    return BIDSLayout(args.bids), df


def inject_dwifmapPhaseEncodingDirection(layout, subsess, args, df):
    for subject, sessions in subsess:

        AP = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='dwi', direction='AP', extension='.nii.gz')
        PA = layout.get(subject=subject, session=sessions, datatype='fmap', acquisition='dwi', direction='PA', extension='.nii.gz')

        if AP:
            for fm in [os.path.join(x.dirname, x.filename) for x in AP]:
                fm_json = fm.replace('.nii.gz', '.json')
                corrected_value = 'j-'

                insert_edit_json(fm_json, 'PhaseEncodingDirection', corrected_value)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'inject_dwifmapPhaseEncodingDirection',
                    'file': os.path.basename(fm_json),
                    'field': 'PhaseEncodingDirection',
                    'original_value': 'n/a',
                    'corrected_value': corrected_value
                })

        if PA:
            for fm in [os.path.join(x.dirname, x.filename) for x in PA]:
                fm_json = fm.replace('.nii.gz', '.json')
                corrected_value = 'j'

                insert_edit_json(fm_json, 'PhaseEncodingDirection', corrected_value)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'inject_dwifmapPhaseEncodingDirection',
                    'file': os.path.basename(fm_json),
                    'field': 'PhaseEncodingDirection',
                    'original_value': 'n/a',
                    'corrected_value': corrected_value
                })

    return BIDSLayout(args.bids), df


def add_PhaseEncodingAxisAndDirection(layout, subsess, args, df):
    for subject, sessions in subsess:

        # PE direction vs axis
        func = layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')

        if func:
            for task in [os.path.join(x.dirname, x.filename) for x in func]:
                task_json = task.replace('.nii.gz', '.json')
                task_metadata = layout.get_metadata(task)

                # add whichever field is missing based on the other
                if "PhaseEncodingAxis" in task_metadata:
                    corrected_value = task_metadata['PhaseEncodingAxis']
                    insert_edit_json(task_json, 'PhaseEncodingDirection', corrected_value)
                    df = df_append(df, {
                        'time': pandas.Timestamp.now(),
                        'function': 'add_PhaseEncodingAxisAndDirection',
                        'file': os.path.basename(task_json),
                        'field': 'PhaseEncodingDirection',
                        'original_value': 'n/a',
                        'corrected_value': corrected_value
                    })

                elif "PhaseEncodingDirection" in task_metadata:
                    corrected_value = task_metadata['PhaseEncodingDirection'].strip('-')
                    insert_edit_json(task_json, 'PhaseEncodingAxis', corrected_value)
                    df = df_append(df, {
                        'time': pandas.Timestamp.now(),
                        'function': 'add_PhaseEncodingAxisAndDirection',
                        'file': os.path.basename(task_json),
                        'field': 'PhaseEncodingAxis',
                        'original_value': 'n/a',
                        'corrected_value': corrected_value
                    })

    return BIDSLayout(args.bids), df


def remove_func_slice_timing(layout, subsess, args, df):
    for subject, sessions in subsess:
        funcs = layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')

        for func in [os.path.join(x.dirname, x.filename) for x in funcs]:
            func_json = func.replace('.nii.gz', '.json')

            if 'SliceTiming' in layout.get_metadata(func):
                with open(func_json, 'r') as f:
                    contents = json.load(f)

                st = deepcopy(contents['SliceTiming'])
                del contents['SliceTiming']

                with open(func_json, 'w') as f:
                    json.dump(contents, f, indent=4)

                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'remove_func_slice_timing',
                    'file': os.path.basename(func_json),
                    'field': 'SliceTiming',
                    'original_value': str(st),
                    'corrected_value': 'REMOVED'
                })

    return BIDSLayout(args.bids), df


def calculate_fmapTotalReadoutTime(layout, subsess, args, df):
    for subject, sessions in subsess:

        fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz')

        if fmaps:
            for fm in [os.path.join(x.dirname, x.filename) for x in fmaps]:
                fm_json = fm.replace('.nii.gz', '.json')
                fm_metadata = layout.get_metadata(fm)

                if 'EffectiveEchoSpacing' in fm_metadata and 'ReconMatrixPE' in fm_metadata:
                    corrected_value = fm_metadata['EffectiveEchoSpacing'] * ( fm_metadata['ReconMatrixPE'] - 1 )
                    insert_edit_json(fm_json, 'TotalReadoutTime', corrected_value)
                    df = df_append(df, {
                        'time': pandas.Timestamp.now(),
                        'function': 'calculate_fmapTotalReadoutTime',
                        'file': os.path.basename(fm_json),
                        'field': 'TotalReadoutTime',
                        'original_value': 'n/a',
                        'corrected_value': corrected_value
                    })

    return BIDSLayout(args.bids), df


def calculate_funcTotalReadoutTime(layout, subsess, args, df):
    for subject, sessions in subsess:

        funcs = layout.get(subject=subject, session=sessions, datatype='func', extension='.nii.gz')

        if funcs:
            for task in [os.path.join(x.dirname, x.filename) for x in funcs]:
                task_json = task.replace('.nii.gz', '.json')
                task_metadata = layout.get_metadata(task)

                if 'EffectiveEchoSpacing' in task_metadata and 'ReconMatrixPE' in task_metadata:
                    corrected_value = task_metadata['EffectiveEchoSpacing'] * ( task_metadata['ReconMatrixPE'] - 1 )
                    insert_edit_json(task_json, 'TotalReadoutTime', corrected_value)
                    df = df_append(df, {
                        'time': pandas.Timestamp.now(),
                        'function': 'calculate_funcTotalReadoutTime',
                        'file': os.path.basename(task_json),
                        'field': 'TotalReadoutTime',
                        'original_value': 'n/a',
                        'corrected_value': corrected_value
                    })

    return BIDSLayout(args.bids), df


def remove_fmap_bval_bvec(layout, subsess, args, df):
    for subject, sessions in subsess:
        fmaps = layout.get(subject=subject, session=sessions, datatype='fmap', extension='.nii.gz')
        for fmap in [os.path.join(x.dirname, x.filename) for x in fmaps]:
            bval = fmap.replace('.nii.gz', '.bval')
            bvec = fmap.replace('.nii.gz', '.bvec')
            if os.path.exists(bval):
                os.remove(bval)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'remove_fmap_bval_bvec',
                    'file': bval,
                    'field': 'n/a',
                    'original_value': os.path.basename(bval),
                    'corrected_value': 'REMOVED'
                })
            if os.path.exists(bvec):
                os.remove(bvec)
                df = df_append(df, {
                    'time': pandas.Timestamp.now(),
                    'function': 'remove_fmap_bval_bvec',
                    'file': bvec,
                    'field': 'n/a',
                    'original_value': os.path.basename(bvec),
                    'corrected_value': 'REMOVED'
                })
        
    return BIDSLayout(args.bids), df


def correct_dwi_bval_floating_point_error(layout, subsess, args, df):
    for subject, sessions in subsess:
        dwis = layout.get(subject=subject, session=sessions, datatype='dwi', extension='.nii.gz')
        for dwi in [os.path.join(x.dirname, x.filename) for x in dwis]:
            bval = dwi.replace('.nii.gz', '.bval')
            if os.path.exists(bval):

                # read the first line of the bval file
                with open(bval, 'r') as f:
                    line = f.readline().rstrip('\n')

                # write in the corrected line
                if '.' in line:
                    newline = ' '.join([ str(int(round(float(b)))) for b in line.strip().split() ])
                    with open(bval, 'w') as f:
                        f.write(newline)

                    df = df_append(df, {
                        'time': pandas.Timestamp.now(),
                        'function': 'correct_dwi_bval_floating_point_error',
                        'file': os.path.basename(bval),
                        'field': 'n/a',
                        'original_value': str(line),
                        'corrected_value': str(newline)
                    })

    return BIDSLayout(args.bids), df


def main():
    # Parse the command line
    args = cli()

    df = pandas.DataFrame(columns=['time', 'function', 'file', 'field', 'original_value', 'corrected_value'])

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

    # add dataset_description.json to the BIDS directory
    dest_ds_desc = args.bids / 'dataset_description.json'
    if not dest_ds_desc.exists():
        shutil.copyfile(ds_desc, dest_ds_desc)
        df = df_append(df, {
            'time': pandas.Timestamp.now(),
            'function': 'main',
            'file': os.path.basename(dest_ds_desc),
            'field': 'n/a',
            'original_value': 'n/a',
            'corrected_value': 'ADDED'
        })

    # add the task JSONs to the BIDS directory
    task_json_root = HERE / 'dependencies/bids'
    for task_json in task_json_root.glob('task-*_bold.json'):
        dest_task_json = args.bids / task_json.name

        if not dest_task_json.exists():
            shutil.copyfile(task_json, dest_task_json)
            df = df_append(df, {
                'time': pandas.Timestamp.now(),
                'function': 'main',
                'file': os.path.basename(dest_task_json),
                'field': 'n/a',
                'original_value': 'n/a',
                'corrected_value': 'ADDED'
            })

    # Load the bids layout
    layout = BIDSLayout(args.bids)
    subsess = read_bids_layout(layout, subject_list=layout.get_subjects(), collect_on_subject=False)
    debug(subsess)

    # check if the DCAN argument was provided
    if args.DCAN != None:
        info("Running all DCAN-Labs/abcd-dicom2bids recommendations")

    # check if the old GE DV25 through DV28 argument was provided
    if args.dwiCorrectOldGE or args.DCAN != None:
        info("Correcting old GE DV25 through DV28 DWI BVAL and BVEC files")
        layout, df = correct_old_GE_DV25_DV28(layout, subsess, args, df)

    # check if the acq-dwi fmap IntendedFor argument was provided
    if args.dwifmapIntendedFor or args.DCAN != None:
        info("Assigning dwi fmap IntendedFor field")
        layout, df = assign_dwifmapIntendedFor(layout, subsess, args, df)
        layout, df = correct_IntendedFor(layout, subsess, args, df)

    # check if the acq-func fmap IntendedFor argument was provided
    # if so, also run the fmapSeparate option
    if args.funcfmapIntendedFor != None or args.DCAN != None:
        info("Separating concatenated field maps")
        layout, df = separate_fmaps(layout, subsess, args, df)

        info("Assigning func fmap IntendedFor fields")
        layout, df = assign_funcfmapIntendedFor(layout, subsess, args, df)
        layout, df = correct_IntendedFor(layout, subsess, args, df)
    # if not and the fmapSeparate option was passed without the funcfmapIntendedFor
    elif args.funcfmapIntendedFor == None and args.fmapSeparate:
        info("Separating concatenated field maps")
        layout, df = separate_fmaps(layout, subsess, args, df)

    # check if the fmap IntendedFor correction argument was provided
    if args.fmapCorrectIntendedFor:
        info("Correcting fmap IntendedFor fields")
        layout, df = correct_IntendedFor(layout, subsess, args, df)

    # check if the anat DwellTime argument was provided
    if args.anatDwellTime or args.DCAN != None:
        info("Injecting anat DwellTime fields")
        layout, df = inject_anatDwellTime(layout, subsess, args, df)

    # check if the dwi fmap TotalReadoutTime argument was provided
    if args.dwiTotalReadoutTime or args.DCAN != None:
        info("Injecting dwi and dwi fmap TotalReadoutTime fields")
        layout, df = inject_dwiTotalReadoutTime(layout, subsess, args, df)

    # check if the dwi fmap EffectiveEchoSpacing argument was provided
    if args.dwiEffectiveEchoSpacing or args.DCAN != None:
        info("Injecting dwi and dwi fmap EffectiveEchoSpacing fields")
        layout, df = inject_dwiEffectiveEchoSpacing(layout, subsess, args, df)

    # check if the func fmap EffectiveEchoSpacing argument was provided
    if args.funcfmapEffectiveEchoSpacing or args.DCAN != None:
        info("Injecting func fmap EffectiveEchoSpacing fields")
        layout, df = inject_funcfmapEffectiveEchoSpacing(layout, subsess, args, df)

    # check if the func EffectiveEchoSpacing argument was provided
    if args.funcEffectiveEchoSpacing or args.DCAN != None:
        info("Injecting func EffectiveEchoSpacing fields")
        layout, df = inject_funcEffectiveEchoSpacing(layout, subsess, args, df)

    # check if the dwi fmap PhaseEncodingDirection argument was provided
    if args.dwifmapPhaseEncodingDirection or args.DCAN != None:
        info("Injecting dwi fmap PhaseEncodingDirection fields")
        layout, df = inject_dwifmapPhaseEncodingDirection(layout, subsess, args, df)

    # check if the PhaseEncoding argument was provided
    if args.funcPhaseEncoding or args.DCAN != None:
        info("Adding PhaseEncodingAxis and Direction fields")
        layout, df = add_PhaseEncodingAxisAndDirection(layout, subsess, args, df)

    # check if the func SliceTiming argument was provided
    if args.funcSliceTimingRemove or args.DCAN != None:
        info("Removing func SliceTiming fields")
        layout, df = remove_func_slice_timing(layout, subsess, args, df)

    if args.dwibvalCorrectFloatingPointError or args.DCAN != None:
        info("Correcting floating point errors in DWI BVAL files")
        layout, df = correct_dwi_bval_floating_point_error(layout, subsess, args, df)
    
    # check if the fmap TotalReadoutTime argument was provided
    if args.fmapTotalReadoutTime or args.DCAN != None:
        info("Calculating fmap TotalReadoutTime fields")
        layout, df = calculate_fmapTotalReadoutTime(layout, subsess, args, df)

    # check if the func TotalReadoutTime argument was provided
    if args.funcTotalReadoutTime or args.DCAN != None:
        info("Calculating func TotalReadoutTime fields")
        layout, df = calculate_funcTotalReadoutTime(layout, subsess, args, df)

    # check if fmap bval/bvec removal argument was provided
    if args.fmapbvalbvecRemove:
        info("Removing field map BVAL and BVEC files")
        layout, df = remove_fmap_bval_bvec(layout, subsess, args, df)

    # save the log
    pipeline_folder = args.bids.parent
    df.to_csv(pipeline_folder / f'code/logs/bids_corrections_log_{pipeline_folder.name}.tsv', sep='\t', index=False)


if __name__ == '__main__':
    main()

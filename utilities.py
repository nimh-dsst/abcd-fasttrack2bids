import argparse
import os
from pathlib import Path

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


def compare_json_files(a, b):
    import json
    with open(a, 'r') as file:
        a_data = json.load(file)
    with open(b, 'r') as file:
        b_data = json.load(file)
    
    if a_data == b_data:
        return 'FULLY EQUAL'

    else:
        a_keys = sorted(list(a_data.keys()))
        b_keys = sorted(list(b_data.keys()))

        if a_keys == b_keys:
            return_string = 'EQUAL KEYS, EQUAL VALUES'

            for key in a_keys:
                if a_data[key] != b_data[key]:
                    print(f'{key} values not equal in (A) {a} VS (B) {b}:')
                    print(f'    (A) {a_data[key]}')
                    print(f'    (B) {b_data[key]}')

                    return_string = 'EQUAL KEYS, NOT EQUAL VALUES'

            return return_string

        else:
            return_string = 'NOT EQUAL KEYS, EQUAL INTERSECTED VALUES'

            a_key_set = set(a_keys)
            b_key_set = set(b_keys)

            a_minus_b = list(a_key_set - b_key_set)
            b_minus_a = list(b_key_set - a_key_set)
            a_intersect_b = list(a_key_set.intersection(b_key_set))

            print(f'Keys in (A) {a} but not in (B) {b}:')
            print(f'    {a_minus_b}')
            print(f'Keys in (B) {b} but not in (A) {a}:')
            print(f'    {b_minus_a}')

            for key in a_intersect_b:
                if a_data[key] != b_data[key]:
                    print(f'{key} values not equal in (A) {a} VS (B) {b}:')
                    print(f'    (A) {a_data[key]}')
                    print(f'    (B) {b_data[key]}')

                    return_string = 'NOT EQUAL KEYS, NOT EQUAL VALUES'

            return return_string


def compare_nifti_files(a, b):
    # Evaluate shape, voxel values, and header information
    import nibabel

    a_data = nibabel.load(a)
    b_data = nibabel.load(b)

    a_img = a_data.get_fdata()
    b_img = b_data.get_fdata()

    if a_data.shape != b_data.shape:
        shape = 'INEQUAL SHAPE'
        return shape
    else:
        shape = 'EQUAL SHAPE'

        if not (a_img == b_img).all():
            values = 'INEQUAL VALUES'
        else:
            values = 'EQUAL VALUES'

        if a_data.header != b_data.header:
            header = 'INEQUAL HEADER'
        else:
            header = 'EQUAL HEADER'

        if a_data.affine != b_data.affine:
            affine = 'INEQUAL AFFINE'
        else:
            affine = 'EQUAL AFFINE'

        return f'{shape}, {values}, {header}, {affine}'

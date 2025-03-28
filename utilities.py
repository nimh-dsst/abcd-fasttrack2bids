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


def evaluate_3d_subvolumes(nifti):
    """
    A function to split a 3D nifti into subvolumes and analyze each.
    uses nibabel and numpy to perform small statistics on the 3D nifti

    Parameters:
    nifti (string): Path to a 3D NIfTI file

    Returns:
    volumes (dict): A dictionary containing the subvolume images and masks
    statistics (dict): A dictionary containing statistics about each subvolume

    """

    import nibabel
    import numpy
    from nilearn.masking import compute_epi_mask

    # Load the nifti file
    img = nibabel.load(nifti)

    # check if the image holds more than 1 timepoint
    if len(img.shape) > 3 and img.shape[3] > 1:
        print("The input NIfTI file must be 3D, not 4D")
        # return None, None, None, None
        return None

    # header = img.header
    # affine = img.affine
    data = img.get_fdata()

    # calculate a whole brain masked volume
    mask_img = compute_epi_mask(img, opening=True)
    mask = mask_img.get_fdata()
    masked_data = numpy.multiply(data, mask)

    # get the center of the volume
    # x_center, y_center, z_center, _ = numpy.linalg.pinv(affine).dot(
    #     numpy.array([0, 0, 0, 1])
    # ).astype(int)

    x_center = int(round(data.shape[0] / 2))
    y_center = int(round(data.shape[1] / 2))
    z_center = int(round(data.shape[2] / 2))

    # R = [i for i in range(x_center, data.shape[0])]
    # A = [i for i in range(y_center, data.shape[1])]
    # S = [i for i in range(z_center, data.shape[2])]
    # L = [i for i in range(0, x_center)]
    # P = [i for i in range(0, y_center)]
    # I = [i for i in range(0, z_center)]

    R = numpy.s_[x_center:]
    A = numpy.s_[y_center:]
    S = numpy.s_[z_center:]
    L = numpy.s_[:x_center]
    P = numpy.s_[:y_center]
    I = numpy.s_[:z_center]

    # create the 8 octant volumes: RAS, RAI, RPS, RPI, LAS, LAI, LPS, and LPI
    # and the anterior and posterior halves
    volumes = {
        'Original': {
            'image': data,
            'mask': mask,
            'masked_image': masked_data,
        },
        'RAS': {
            'image': data[R, A, S],
            'mask':  mask[R, A, S],
            'masked_image': masked_data[R, A, S],
        },
        'RAI': {
            'image': data[R, A, I],
            'mask':  mask[R, A, I],
            'masked_image': masked_data[R, A, I],
        },
        'RPS': {
            'image': data[R, P, S],
            'mask':  mask[R, P, S],
            'masked_image': masked_data[R, P, S],
        },
        'RPI': {
            'image': data[R, P, I],
            'mask':  mask[R, P, I],
            'masked_image': masked_data[R, P, I],
        },
        'LAS': {
            'image': data[L, A, S],
            'mask':  mask[L, A, S],
            'masked_image': masked_data[L, A, S],
        },
        'LAI': {
            'image': data[L, A, I],
            'mask':  mask[L, A, I],
            'masked_image': masked_data[L, A, I],
        },
        'LPS': {
            'image': data[L, P, S],
            'mask':  mask[L, P, S],
            'masked_image': masked_data[L, P, S],
        },
        'LPI': {
            'image': data[L, P, I],
            'mask':  mask[L, P, I],
            'masked_image': masked_data[L, P, I],
        },
        'Anterior': {
            'image': data[:, A, :],
            'mask':  mask[:, A, :],
            'masked_image': masked_data[:, A, :],
        },
        'Posterior': {
            'image': data[:, P, :],
            'mask':  mask[:, P, :],
            'masked_image': masked_data[:, P, :],
        },
        'Anterior-Inferior': {
            'image': data[:, A, I],
            'mask':  mask[:, A, I],
            'masked_image': masked_data[:, A, I],
        },
        'Posterior-Inferior': {
            'image': data[:, P, I],
            'mask':  mask[:, P, I],
            'masked_image': masked_data[:, P, I],
        },
    }

    # create a dictionary to store the statistics
    statistics = {}
    for key in volumes.keys():
        statistics[key] = {
            'shape': volumes[key]['image'].shape,
            'mask_sum': numpy.sum(volumes[key]['mask']),
            'image_mean': numpy.mean(volumes[key]['image']),
            'image_std': numpy.std(volumes[key]['image']),
            'image_min': numpy.min(volumes[key]['image']),
            'image_max': numpy.max(volumes[key]['image']),
            'masked_image_mean': numpy.mean(volumes[key]['masked_image']),
            'masked_image_std': numpy.std(volumes[key]['masked_image']),
            'masked_image_max': numpy.max(volumes[key]['masked_image']),
        }

    # return header, affine, volumes, statistics
    return statistics

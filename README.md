# ABCD NDA Fast Track to BIDS conversion tools

## Installation

1. Install [Python 3.8](https://www.python.org/downloads/) (or above).
1. Install [pipx](https://pipxproject.github.io/pipx/).

    ```shell
    python3 -m pip install --user pipx
    python3 -m pipx ensurepath
    ```

1. Install [Poetry](https://python-poetry.org/docs/).

    ```shell
    pipx install --user poetry
    ```

1. Clone this repository.

    ```shell
    git clone https://github.com/nimh-dsst/abcd-fasttrack2bids.git
    ```

1. Change into the repository directory.

    ```shell
    cd abcd-fasttrack2bids
    ```

1. Install the Python dependencies.

    ```shell
    poetry install
    ```

## Resource Request Guidance for `pipeline.py`

### Memory

Request double the amount of concurrent conversions you do (with `--n-convert` or `--n-all`) for Memory (in GB). In other words, if you request `--n-all` or `--n-convert` of 10, request 20 GB of Memory for the whole process. This is because the `dcm2bids` which uses `dcm2niix` process is somehwat memory-intensive and can use up to 2 GB per concurrent conversion.

### Disk Space per participant-session

- **Downloaded TGZs**: ~### GB
- **Unpacked DICOMs**: ~### GB
- **BIDS Data**: ~2.5 GB
- **Temporary Space**: ~12 GB

## CPUs/threads

You can control the number of concurrent downloads, unpackings, and conversions you want to run with the `--n-download`, `--n-unpack`, and `--n-convert` arguments. Alternatively, you can set all three to the same thing with `--n-all`. This allows for separately specifying the allowed concurrency on your own local system. For instance, at NIH we use only 6 concurrent downloads to be resepctful of the filesystem and network bandwidth, but 12 concurrent unpackings and 12 concurrent conversions to speed up the the very parallel processes.

## Time to download, unpack, and convert

FILL IN THE BLANK.

## Examples

### `fasttrack2s3.py`

1. Filter by default all series (except quality assurance series) from the `~/abcd_fastqc01.txt` file only including the participant-sessions in `~/sessions.csv`, then output the filtered `abcd_fastqc01.txt` files and S3 links to the `~/abcdfasttrack` output directory as both combined and separate files per participant-session (thanks to the `-sep` option).

    ```bash
    cd ~/abcd-fasttrack2bids
    poetry run python fasttrack2s3.py -csv ~/sessions.csv -sep ~/abcd_fastqc01.txt ~/abcdfasttrack
    ```

### `pipeline.py`

1. Preserving the LOGS files and BIDS data while using 12 download worker threads, 20 concurrent TGZ unpackings, and 25 MRI sessions going through dcm2bids concurrently. This also uses the `dcm2bids_v3_config.json` configuration file, the NDA package 1234567, the `~/abcd_fastqc01_all_p-20_s-25_s3links.txt` S3 links file, a temporary directory of `/scratch/abcd`, and outputs at the end to the `~/all_p-20_s-25` directory.

    ```bash
    cd ~/abcd-fasttrack2bids
    poetry run python pipeline.py -p 1234567 -s ~/abcd_fastqc01_all_p-20_s-25_s3links.txt -c dcm2bids_v3_config.json -t /scratch/abcd -o ~/all_p-20_s-25 -z LOGS BIDS --n-download 12 --n-unpack 20 --n-convert 25
    ```

1. Download the TGZs and unpack them for the DICOMs while only saving the logs and DICOM files. This uses the NDA package 1234567, the `~/sub-NDARINVANONYMIZED_ses-2YearFollowUpYArm1_s3links.txt` S3 links file, the `dcm2bids_v3_config.json` Dcm2Bids configuration file, and outputs to the `~/all_p-1_s-1` directory. This also runs all steps with 5 concurrent parallel commands.

    ```bash
    cd ~/abcd-fasttrack2bids
    poetry run python pipeline.py -p 1234567 -s ~/sub-NDARINVANONYMIZED_ses-2YearFollowUpYArm1_s3links.txt -c dcm2bids_v3_config.json -o ~/all_p-1_s-1 -z LOGS DICOM --n-all 5
    ```

### `bids_corrections.py`

1. Correct the BIDS dataset using the "DCAN Labs corrections" at `~/all_p-20_s-25/rawdata` using the temporary directory of `/scratch/abcd`, logging to `~/all_p-20_s-25/code/logs`, and using the the MCR v9.1 (MATLAB R2016b compiler runtime environment) directory at `~/MCR/v91`.

    ```bash
    cd ~/abcd-fasttrack2bids
    poetry run python bids_corrections.py -b ~/all_p-20_s-25/rawdata -t /scratch/abcd -l ~/all_p-20_s-25/code/logs --DCAN ~/MCR/v91
    ```

## Acknowledgements

Thanks to [`DCAN-Labs/abcd-dicom2bids`](https://github.com/DCAN-Labs/abcd-dicom2bids) for:

1. Inspiration of the dcm2bids version 3 configuration JSON
1. General order of operations for the NDA's fast track conversion to BIDS
1. Most of the options in `bids_corrections.py`

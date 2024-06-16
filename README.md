# ABCD NDA Fast Track to BIDS conversion tools

## To Do

### `fasttrack2s3.py` - Fast Track Filter

- [ ] **Make "special" inclusions and exclusions, like "Replaced" or ftq_complete==1, easier to do.**
- [ ] Add flag to grab `--only-new` given a DSST ABCD fast-track `scans.tsv` file.
- [ ] Add additonal option to save out logs to a specific file.
- [ ] Add levels of log messages of warning/caution for the user to know what's going on with datatypes specifically.

### `pipeline.py` - Download --> Unpack --> Convert Pipeline

- [x] ~~Fix the event file copies to the `sourcedata` directory to be numbered correctly among many subjects.~~
- [ ] Don't halt the whole pipeline if a single session fails to convert.
- [ ] Don't halt the whole pipeline if a single session's single series fails to convert.
- [ ] Make the script take as input either a single `s3links.txt` file, or a directory of them (to prepare for swarm submission).
- [ ] Add a flag to optionally run bids-validator on the output BIDS directory.
- [ ] Implement the `--n-all` option (it's not tied to anything right now...)

### `bids_corrections.py` - Automated BIDS Corrections

- [ ] Add a flag to optionally run bids-validator on the output BIDS directory.

### `README.md` - This file

- [ ] Improve this `README.md` with a walkthrough of preparing the two NDA packages necessary for using this.

### Testing

- [ ] Test `pipeline.py` on a mixed set of sessions, including some same-participant-different-sessions.
- [ ] Test `pipeline.py` stops before executing the convert workflow if BIDS is not provided in the `--preserve` option.
- [ ] Test `pipeline.py` stops before executing the unpack workflow if both BIDS and TGZ are not provided in the `--preserve` option.

## Operating Procedure

Each numbered part of this list is one tool, which can be used independently. I will build a common usage pipeline out of it.

1. `fasttrack2s3.py`: Filter down the `abcd_fastqc01.txt` file based on user selection of data types, participants, and sessions, then output an `s3_links.txt`.
1. NDA Tools' `downloadcmd` on all the links in `s3_links.txt`, output to a single directory. Or maybe just use `downloadcmd` as-is?
1. ABCD DICOM TGZ unpack.
1. Dcm2Bids (v3) across all available unpacked DICOMs.
1. Grab unpacked event timing files and put them in the BIDS `sourcedata` directory.
1. (stretch goal) Ingest BIDS sidecar metadata from the DAIRC present in the unpacked TGZs
1. (optional) Automated sidecar JSON corrections for "EffectiveEchoSpacing".
1. (optional) Use bids-validator to log the validity of output data.

## Improvement Ideas

- Perhaps add arguments to a top-level wrapper, `fasttrack2bids.py`, to allow for controlling the overall workflow with some sane defaults and running options.

## Examples

### `fasttrack2s3.py`

### `pipeline.py`

1. Preserving the LOGS files and BIDS data while using 12 download worker threads, 20 concurrent TGZ unpackings, and 25 MRI sessions going through dcm2bids concurrently. This also uses the `dcm2bids_v3_config.json` configuration file, the NDA package 1234567, the `~/abcd_fastqc01_all_p-20_s-25_s3links.txt` S3 links file, and outputting to the `~/all_p-20_s-25` directory.

    ```bash
    cd ~/abcd-fasttrack2bids
    poetry run python pipeline.py -p 1234567 -s ~/abcd_fastqc01_all_p-20_s-25_s3links.txt -c dcm2bids_v3_config.json -o ~/all_p-20_s-25 -z LOGS BIDS --n-download 12 --n-unpack 20 --n-convert 25
    ```

### `bids_corrections.py`

## Acknowledgements

Thanks to [`DCAN-Labs/abcd-dicom2bids`](https://github.com/DCAN-Labs/abcd-dicom2bids) for:

1. Inspiration of the dcm2bids version 3 configuration JSON
1. General order of operations for the NDA's fast track conversion to BIDS
1. Most of the options in `bids_corrections.py`

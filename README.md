# ABCD NDA Fast Track to BIDS conversion tools

## To do

- [ ] Give credit to DCAN-Labs/abcd-dicom2bids for inspiration of the dcm2bids config JSON.
- [x] ~~Create a fast track to s3 link filter script.~~
- [ ] Execute plan for `downloadcmd`, `tar xzf`, and `dcm2bids`.

## Plan

Each numbered part of this list is one tool, which can be used independently. I will build a common usage pipeline out of it.

1. `fasttrack2s3.py`: Filter down the `abcd_fastqc01.txt` file based on user selection of data types, participants, and sessions, then output an `s3_links.txt`.
1. NDA Tools' `downloadcmd` on all the links in `s3_links.txt`, output to a single directory. Or maybe just use `downloadcmd` as-is?
1. ABCD DICOM TGZ unpack.
1. Dcm2Bids (v3) across all available unpacked DICOMs.
1. (stretch goal) Ingest BIDS sidecar metadata from the DAIRC present in the unpacked TGZs
1. (optional) Automated sidecar JSON corrections for "EffectiveEchoSpacing".
1. (optional) Use bids-validator to log the validity of output data.

## Ideas

- Perhaps add arguments to a top-level wrapper, `fasttrack2bids.py`, to allow for specifying
  - `--n-download 6` for 6 worker threads downloading with `downloadcmd`
  - `--n-unpack 16` for 16 parallel TGZ unpacks with `tar xzf`
  - `--n-dcm2bids 100` for 100 parallel runs of `dcm2bids`

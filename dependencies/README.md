# Dependencies to run bids_corrections.py

These dependencies are required for the time being until the eta_squared binary can be replaced with a Python implementation.

- `__init__.py`: Empty file to make Python treat the directory as containing packages.
- `FSL_identity_transformation_matrix.mat`: FSL identity matrix copied, from https://github.com/DCAN-Labs/abcd-dicom2bids/commit/73196473d91973f015368678263b49de68a130c3
- `eta_squared`: MATLAB compiled binary file to calculate eta squared between two images, from https://github.com/DCAN-Labs/abcd-dicom2bids/commit/73196473d91973f015368678263b49de68a130c3
- `run_eta_squared.sh`: Shell script used to run `eta_squared` binary, from https://github.com/DCAN-Labs/abcd-dicom2bids/commit/afca86bd69c695952a1409ccc77c3f85a62b7101
- `sefm_eval_and_json_editor.py`: Python script from which to pull spin-echo field map selection and other functions, first copied from https://github.com/DCAN-Labs/abcd-dicom2bids/commit/90764095cde2b93eb18b2437aff953302c106d0e

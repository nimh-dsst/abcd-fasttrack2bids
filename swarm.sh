#! /bin/bash

# initialize inputs
ABCD_FASTQC01=/data/NIMH_scratch/zwallymi/earlea-d2b/fastqc/20240501_abcd_fastqc01.txt
BIDS_OUTPUT_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/testing_chain
MCR91_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/abcd-dicom2bids/env_setup/MCR_v9.1/v91
NDA_PACKAGE_ID=1228006
SESSIONS_CSV=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/small_sessions.csv
LOG_BASEDIR=/data/NIMH_scratch/zwallymi/earlea-d2b/logs

# cleanup pre-run to allow all files to be downloaded, this also gest around a bug in downloadcmd
echo "### Cleaning out the download progress file to allow all files to be downloaded ###"
DOWNLOAD_PROGRESS_DIR=~/NDA/nda-tools/downloadcmd/packages/${NDA_PACKAGE_ID}/.download-progress
mkdir -p ${DOWNLOAD_PROGRESS_DIR}
rm -rf ${DOWNLOAD_PROGRESS_DIR}/*

# run the fasttrack2s3.py script
echo "### Running the fasttrack2s3.py script ###"

CODE_DIR=$(readlink -f `dirname $0`)
TEMP_BASENAME=`date '+%Y-%m-%d'`_`head /dev/urandom | tr -dc A-Z1-9 | head -c8`
LOG_DIR=${LOG_BASEDIR}/${TEMP_BASENAME}
mkdir -p $LOG_DIR
poetry run --directory ${CODE_DIR} python ${CODE_DIR}/fasttrack2s3.py -sep -csv ${SESSIONS_CSV} ${ABCD_FASTQC01} ${LOG_DIR}

# create the swarm file
echo "### Creating the swarm file ###"

BIDS_OUTPUT_BASENAME=`basename ${BIDS_OUTPUT_DIR}`
SWARM_FILE=${LOG_DIR}/${BIDS_OUTPUT_BASENAME}.swarm
cp ${CODE_DIR}/header.swarm ${SWARM_FILE}
echo "#SWARM --logdir ${LOG_DIR}" >> ${SWARM_FILE}

# for each s3links file (each separated session) in the LOG_DIR, run the pipeline, bids_corrections, and rsync back
for LINK in ${LOG_DIR}/*/*_s3links.txt ; do
    CMD1="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/pipeline.py -p ${NDA_PACKAGE_ID} -c ${CODE_DIR}/dcm2bids_v3_config.json -z LOGS BIDS --n-download 2 --n-unpack 2 --n-convert 1 -o /lscratch/\${SLURM_JOB_ID} -s ${LINK}"
    CMD2="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/bids_corrections.py -b /lscratch/\${SLURM_JOB_ID}/rawdata -t /lscratch/\${SLURM_JOB_ID} --dwiCorrectOldGE --funcfmapIntendedFor ${MCR91_DIR}"
    CMD3="for BIDS in code rawdata sourcedata ; do if [ -d /lscratch/\${SLURM_JOB_ID}/\${BIDS} ] ; then rsync -art /lscratch/\${SLURM_JOB_ID}/\${BIDS} ${BIDS_OUTPUT_DIR}/ ; fi ; done"

    echo "${CMD1} ; ${CMD2} ; echo rsyncing data back from /lscratch/\${SLURM_JOB_ID} ; ${CMD3} ; echo rsync completed to ${BIDS_OUTPUT_DIR}" >> ${SWARM_FILE}
done

echo "### The following command is printed for your convenience, but not run yet ###"
echo "swarm ${SWARM_FILE}"

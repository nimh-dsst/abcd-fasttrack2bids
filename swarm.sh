#! /bin/bash

# initialize inputs
BIDS_BASEDIR=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/current_dwi_20240708
SESSIONS_CSV=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/current_dwi_20240708/unsuccessfully_converted_sessions_round_02.csv
# CORRECTION_OPTIONS="--dwiCorrectOldGE --funcSliceTimingRemove --dwibvalCorrectFloatingPointError --fmapTotalReadoutTime --funcTotalReadoutTime --fmapbvalbvecRemove --funcfmapIntendedFor ${MCR91_DIR}"
CORRECTION_OPTIONS="--dwiCorrectOldGE --dwibvalCorrectFloatingPointError"
# DATATYPE_OPTIONS="all"
DATATYPE_OPTIONS="only-dwi"
# PIPELINE_OPTIONS=""
PIPELINE_OPTIONS="-d"
NDA_PACKAGE_ID=1230191

ABCD_FASTQC01=/data/NIMH_scratch/zwallymi/earlea-d2b/fastqc/20240501_abcd_fastqc01.txt
LOG_BASEDIR=/data/NIMH_scratch/zwallymi/earlea-d2b/logs
MCR91_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/abcd-dicom2bids/env_setup/MCR_v9.1/v91

#####################################
### DO NOT MODIFY BELOW THIS LINE ###
#####################################

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
poetry run --directory ${CODE_DIR} python ${CODE_DIR}/fasttrack2s3.py -d ${DATATYPE_OPTIONS} -sep -csv ${SESSIONS_CSV} ${ABCD_FASTQC01} ${LOG_DIR}

# create the swarm file
echo "### Creating the swarm file ###"

ABCD_FASTQC01_BASENAME=`basename ${ABCD_FASTQC01} | sed 's|\(.\+\)\..\+|\1|'`
S3LINKS_COMPLETE_FILE=`ls -d ${LOG_DIR}/${ABCD_FASTQC01_BASENAME}_*_s3links.txt`
OUTPUT_SUFFIX=`basename ${S3LINKS_COMPLETE_FILE} | sed "s|${ABCD_FASTQC01_BASENAME}_||g" | sed "s|_s3links.txt||g"`
BIDS_OUTPUT_DIR=${BIDS_BASEDIR}/${OUTPUT_SUFFIX}
mkdir -p ${BIDS_OUTPUT_DIR}

OUTPUT_PREFIX=`basename ${BIDS_BASEDIR}`
SWARM_FILE=${LOG_DIR}/${OUTPUT_PREFIX}_${OUTPUT_SUFFIX}.swarm
cp ${CODE_DIR}/header.swarm ${SWARM_FILE}
echo "#SWARM --logdir ${LOG_DIR}" >> ${SWARM_FILE}

# for each s3links file (each separated session) in the LOG_DIR, run the pipeline, bids_corrections, and rsync back
for LINK in ${LOG_DIR}/*/*_s3links.txt ; do
    CMD1="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/pipeline.py ${PIPELINE_OPTIONS} -p ${NDA_PACKAGE_ID} -c ${CODE_DIR}/dcm2bids_v3_config.json -z LOGS BIDS --n-download 2 --n-unpack 2 --n-convert 1 -o /lscratch/\${SLURM_JOB_ID} -s ${LINK}"
    CMD2="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/bids_corrections.py -b /lscratch/\${SLURM_JOB_ID}/rawdata -t /lscratch/\${SLURM_JOB_ID} ${CORRECTION_OPTIONS}"
    CMD3="for BIDS in code rawdata sourcedata ; do if [ -d /lscratch/\${SLURM_JOB_ID}/\${BIDS} ] ; then echo rsyncing from /lscratch/\${SLURM_JOB_ID}/\${BIDS} ; rsync -art /lscratch/\${SLURM_JOB_ID}/\${BIDS} ${BIDS_OUTPUT_DIR}/ ; echo cleaning out /lscratch/\${SLURM_JOB_ID}/\${BIDS} ; rm -rf /lscratch/\${SLURM_JOB_ID}/\${BIDS} ; fi ; done"

    echo "${CMD1} ; ${CMD2} ; ${CMD3} ; echo rsync completed to ${BIDS_OUTPUT_DIR}" >> ${SWARM_FILE}
done

echo "### The following command is printed for your convenience, but not run yet ###"
echo "swarm --devel ${SWARM_FILE}"

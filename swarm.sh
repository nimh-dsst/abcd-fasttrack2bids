#! /bin/bash

######################################################
### vvv This is the start of the input section vvv ###
######################################################

# The base directory where the BIDS data will be stored
BIDS_BASEDIR=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/current_dwi_20240708

# The comma-separated value file containing the subject,session information expected in fasttrack2s3.py
SESSIONS_CSV=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/current_dwi_20240708/unsuccessfully_converted_sessions_round_03.csv

# This is the NDA package ID for the data to be downloaded with downloadcmd in pipeline.py
NDA_PACKAGE_ID=1230191

# The path to the abcd_fastqc01.txt file downloaded as-is from the NDA
ABCD_FASTQC01=/data/NIMH_scratch/zwallymi/earlea-d2b/fastqc/20240501_abcd_fastqc01.txt

# The base directory where the swarm logs will be stored
LOG_BASEDIR=/data/NIMH_scratch/zwallymi/earlea-d2b/logs

# The MATLAB Compiler Runtime Environment (MCR) directory for the installed MCR version 9.1 (MATLAB R2016b)
MCR91_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/abcd-dicom2bids/env_setup/MCR_v9.1/v91

# These are the space-separated options for the fasttrack2s3.py desired data types
DATATYPE_OPTIONS="only-dwi"
# DATATYPE_OPTIONS="all"

# This will typically be empty for subjects with fMRI data present, the -d flag is for when there's no func data
PIPELINE_OPTIONS="-d"
# PIPELINE_OPTIONS=""

# These are the space-separated options for the bids_corrections.py script to choose corrections to apply
CORRECTION_OPTIONS="--dwiCorrectOldGE --dwibvalCorrectFloatingPointError"
# CORRECTION_OPTIONS="--dwiCorrectOldGE --funcSliceTimingRemove --dwibvalCorrectFloatingPointError --fmapTotalReadoutTime --funcTotalReadoutTime --fmapbvalbvecRemove --funcfmapIntendedFor ${MCR91_DIR}"

####################################################
### ^^^ This is the end of the input section ^^^ ###
####################################################

#####################################
### DO NOT MODIFY BELOW THIS LINE ###
#####################################

# run the fasttrack2s3.py script
echo `date` "### Running the fasttrack2s3.py script ###"

CODE_DIR=$(readlink -f `dirname $0`)
TEMP_BASENAME=`date '+%Y-%m-%d'`_`head /dev/urandom | tr -dc A-Z1-9 | head -c8`
LOG_DIR=${LOG_BASEDIR}/${TEMP_BASENAME}
mkdir -p $LOG_DIR
poetry run --directory ${CODE_DIR} python ${CODE_DIR}/fasttrack2s3.py -d ${DATATYPE_OPTIONS} -sep -csv ${SESSIONS_CSV} ${ABCD_FASTQC01} ${LOG_DIR}

# create the swarm file
echo `date` "### Creating the swarm file ###"

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
    CMD0="DOWNLOADCMD_PATH=/lscratch/\${SLURM_JOB_ID}/pip_install ; mkdir \${DOWNLOADCMD_PATH} ; poetry run --directory ${CODE_DIR} python -m pip install nda-tools -t \${DOWNLOADCMD_PATH} ; poetry run --directory ${CODE_DIR} python ${CODE_DIR}/fix_downloadcmd.py \${DOWNLOADCMD_PATH} ; cp \${DOWNLOADCMD_PATH}/bin/downloadcmd \${DOWNLOADCMD_PATH}/  ; export PATH=\${DOWNLOADCMD_PATH}:\${PATH}"
    CMD1="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/pipeline.py ${PIPELINE_OPTIONS} -p ${NDA_PACKAGE_ID} -c ${CODE_DIR}/dcm2bids_v3_config.json -z LOGS BIDS --n-download 2 --n-unpack 2 --n-convert 1 -o /lscratch/\${SLURM_JOB_ID} -s ${LINK}"
    CMD2="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/bids_corrections.py -b /lscratch/\${SLURM_JOB_ID}/rawdata -t /lscratch/\${SLURM_JOB_ID} ${CORRECTION_OPTIONS}"
    CMD3="for BIDS in code rawdata sourcedata ; do if [ -d /lscratch/\${SLURM_JOB_ID}/\${BIDS} ] ; then echo rsyncing from /lscratch/\${SLURM_JOB_ID}/\${BIDS} ; rsync -art /lscratch/\${SLURM_JOB_ID}/\${BIDS} ${BIDS_OUTPUT_DIR}/ ; echo cleaning out /lscratch/\${SLURM_JOB_ID}/\${BIDS} ; rm -rf /lscratch/\${SLURM_JOB_ID}/\${BIDS} ; fi ; done"

    echo "${CMD0} ; ${CMD1} ; ${CMD2} ; ${CMD3} ; echo rsync completed to ${BIDS_OUTPUT_DIR}" >> ${SWARM_FILE}
done

echo `date` "### The following command is printed for your convenience, but not run yet ###"
echo "swarm --devel ${SWARM_FILE}"

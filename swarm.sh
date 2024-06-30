#! /bin/bash

SWARM_LOG_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/logs/fasttrack2bids
BIDS_OUTPUT_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/testing_chain
CODE_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/fasttrack2bids
S3LINKS_DIR=/data/NIMH_scratch/zwallymi/earlea-d2b/downloads/20240501_abcd_fastqc01_all_p-20_s-25

mkdir -p $SWARM_LOG_DIR
OUTPUT_BASENAME=`basename ${BIDS_OUTPUT_DIR}`
cp ${CODE_DIR}/header.swarm ${SWARM_LOG_DIR}/${OUTPUT_BASENAME}.swarm

echo "#SWARM --logdir ${SWARM_LOG_DIR}" >> ${SWARM_LOG_DIR}/${OUTPUT_BASENAME}.swarm

for LINK in ${S3LINKS_DIR}/*_s3links.txt ; do
    CMD1="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/pipeline.py -p 1228006 -c ${CODE_DIR}/dcm2bids_v3_config.json -z LOGS BIDS --n-download 2 --n-unpack 2 --n-convert 1 -o /lscratch/\${SLURM_JOB_ID} -s ${LINK}"
    CMD2="poetry run --directory ${CODE_DIR} python ${CODE_DIR}/bids_corrections.py -b /lscratch/\${SLURM_JOB_ID}/rawdata -t /lscratch/\${SLURM_JOB_ID} --dwiCorrectOldGE --funcfmapIntendedFor /data/NIMH_scratch/zwallymi/earlea-d2b/abcd-dicom2bids/env_setup/MCR_v9.1/v91"
    CMD3="for BIDS in code rawdata sourcedata ; do if [ -d /lscratch/\${SLURM_JOB_ID}/\${BIDS} ] ; then rsync -art /lscratch/\${SLURM_JOB_ID}/\${BIDS} ${BIDS_OUTPUT_DIR}/ ; fi ; done"

    echo "${CMD1} ; ${CMD2} ; echo rsyncing data back from /lscratch/\${SLURM_JOB_ID} ; ${CMD3} ; echo rsync completed to ${BIDS_OUTPUT_DIR}" >> ${SWARM_LOG_DIR}/${OUTPUT_BASENAME}.swarm
done

echo "swarm ${SWARM_LOG_DIR}/${OUTPUT_BASENAME}.swarm"

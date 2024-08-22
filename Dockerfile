FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive

#-------------------------------------------------------------------------------
# Install common dependencies
#-------------------------------------------------------------------------------

    RUN apt update && apt install -yq --no-install-recommends \
        apt-utils \
        ca-certificates \
        git \
        rsync \
        unzip \
        python3.10 \
        python3-pip \
        wget

#-------------------------------------------------------------------------------
# Install python poetry
#-------------------------------------------------------------------------------

    RUN python3 -m pip install poetry

#-------------------------------------------------------------------------------
# Clone the repository
#-------------------------------------------------------------------------------

    WORKDIR /opt

    RUN git clone -b v1.0.0 --single-branch --depth 1 \
        https://github.com/nimh-dsst/abcd-fasttrack2bids.git abcd-fasttrack2bids

#-------------------------------------------------------------------------------
# Install the python dependencies
#-------------------------------------------------------------------------------

    WORKDIR /opt/abcd-fasttrack2bids

    RUN poetry install

#-------------------------------------------------------------------------------
# Install MATLAB Compiler Runtime
#-------------------------------------------------------------------------------

    RUN mkdir -p /opt/mcr /opt/mcr_download

    WORKDIR /opt/mcr_download

    RUN wget https://ssd.mathworks.com/supportfiles/downloads/R2016b/deployment_files/R2016b/installers/glnxa64/MCR_R2016b_glnxa64_installer.zip \
        && unzip MCR_R2016b_glnxa64_installer.zip \
        && ./install -agreeToLicense yes -mode silent -destinationFolder /opt/mcr \
        && rm -rf /opt/mcr_download

#-------------------------------------------------------------------------------
# Set environment variables
#-------------------------------------------------------------------------------

    ENV LD_LIBRARY_PATH="/opt/mcr/v91/runtime/glnxa64:/opt/mcr/v91/bin/glnxa64:/opt/mcr/v91/sys/os/glnxa64:$LD_LIBRARY_PATH" \
        OMP_NUM_THREADS=1 \
        TMPDIR=/tmp

#-------------------------------------------------------------------------------
# Set up the entrypoint
#-------------------------------------------------------------------------------

    COPY ["./entrypoint.sh", "/entrypoint.sh"]

    RUN chmod 775 /entrypoint.sh

    ENTRYPOINT ["/entrypoint.sh"]

#-------------------------------------------------------------------------------
# Configure the default command
#-------------------------------------------------------------------------------

    WORKDIR /

    CMD ["--help"]

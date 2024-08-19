FROM ubuntu/python:3.10-22.04_stable
ARG DEBIAN_FRONTEND=noninteractive

#-------------------------------------------------------------------------------
# Install common dependencies
#-------------------------------------------------------------------------------

    RUN apt-get update && apt-get install -yq --no-install-recommends \
        git \
        rsync \
        unzip \
        wget
        # apt-utils \
        # build-essential \
        # bzip2 \
        # ca-certificates \
        # curl \
        # dirmngr\
        # gnupg2 \
        # libglib2.0-0 \
        # libssl1.0.0\
        # libssl-dev\
        # locales \
        # m4 \
        # make \
        # python-pip \

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
# Install python poetry
#-------------------------------------------------------------------------------

    RUN pip install poetry

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
# Set environment variables
#-------------------------------------------------------------------------------

    ENV OMP_NUM_THREADS=1
    ENV TMPDIR=/tmp

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

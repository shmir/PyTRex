# docker build -t trex:89 -f Dockerfile .
# docker run --privileged-ti trex:89 /bin/bash
# docker run  --privileged -itd --cap-add=ALL -p 8090:8090 -p 4500:4500 -p 4501:4501 -p 4507:4507 --name trex trex:89
# docker exec --privileged -d trex sh -c "/etc/create_two_veth ; cd /v2.89 ; sudo ./t-rex-64 -i"

FROM ubuntu:18.04
RUN apt-get update
RUN apt-get -y install python3 \
             python3-pip \
             wget \
             bash \
             net-tools \
             netbase \
             strace \
             iproute2 \
             iputils-ping \
             pciutils \
             vim \
             sudo \
             bridge-utils

RUN wget --no-check-certificate https://trex-tgn.cisco.com/trex/release/v2.89.tar.gz && \
    tar -zxvf v2.89.tar.gz -C / && \
    chown root:root /v2.89  && \
    rm v2.89.tar.gz

COPY create_two_veth /etc/create_two_veth
COPY trex_cfg.yaml /etc/trex_cfg.yaml
RUN chmod 777 /etc/create_two_veth

FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG NPU_ARCHIVE_SHA256=48cc219a5bd882a7cadaef523d9bb0c1e03c1b9b5b8562a29ad5ee4b9bfbb3bc
ARG LEVEL_ZERO_SHA256=526808b420a2bd7b4ee24a99e9a71a35de820abe3e33c22dcb51c490da4439e0
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq \
    && apt-get install -y -qq ca-certificates curl libtbb12 python3 python3-venv \
    && curl -fsSL --retry 3 \
      https://github.com/intel/linux-npu-driver/releases/download/v1.33.0/linux-npu-driver-v1.33.0.20260529-26625960453-ubuntu2404.tar.gz \
      -o /tmp/npu.tar.gz \
    && echo "${NPU_ARCHIVE_SHA256}  /tmp/npu.tar.gz" | sha256sum -c - \
    && mkdir /tmp/npu && tar -xf /tmp/npu.tar.gz -C /tmp/npu \
    && apt-get install -y -qq /tmp/npu/*.deb \
    && curl -fsSL --retry 3 \
      https://snapshot.ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/20260324T100000Z/pool/main/l/level-zero-loader/libze1_1.27.0-1~24.04~ppa2_amd64.deb \
      -o /tmp/libze1.deb \
    && echo "${LEVEL_ZERO_SHA256}  /tmp/libze1.deb" | sha256sum -c - \
    && apt-get install -y -qq /tmp/libze1.deb \
    && python3 -m venv /opt/openvino \
    && /opt/openvino/bin/pip install --no-cache-dir \
      numpy==2.4.6 openvino-telemetry==2025.2.0 openvino==2026.2.0 \
    && rm -rf /var/lib/apt/lists/* /tmp/npu /tmp/npu.tar.gz /tmp/libze1.deb

COPY probe.py /opt/fam/probe.py
ENTRYPOINT ["/opt/openvino/bin/python", "/opt/fam/probe.py"]

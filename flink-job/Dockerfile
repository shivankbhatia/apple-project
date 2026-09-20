FROM flink:1.18.1-scala_2.12-java11

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-dev \
        openjdk-11-jdk-headless \
        build-essential \
    && ln -s /usr/lib/jvm/java-11-openjdk-arm64/include /opt/java/openjdk/include \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-arm64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PYFLINK_PYTHON=/usr/bin/python3
ENV PYFLINK_CLIENT_EXECUTABLE=/usr/bin/python3

RUN pip3 install --no-cache-dir \
    apache-flink==1.18.1 \
    xgboost \
    kafka-python
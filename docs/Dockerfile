ARG python_version
FROM python:${python_version}-slim

ARG TARGETARCH
ARG drawio_version

COPY --chmod=755 entrypoint.sh /
EXPOSE 8000
WORKDIR /mkdocs
ENTRYPOINT ["/entrypoint.sh"]
CMD ["build"]

COPY build.sh .
COPY requirements.txt .
RUN ["/bin/bash", "-x", "build.sh"]
RUN rm -f build.sh requirements.txt

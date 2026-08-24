ARG HOUSE_BRAIN_BASE_IMAGE=ghcr.io/vince87/house-brain:0.1.6
FROM ${HOUSE_BRAIN_BASE_IMAGE}

COPY addon_launcher.py /usr/local/bin/house-brain-addon
RUN chmod 755 /usr/local/bin/house-brain-addon

ENTRYPOINT ["/usr/local/bin/house-brain-addon"]

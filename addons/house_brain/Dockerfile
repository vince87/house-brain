FROM ghcr.io/vince87/house-brain:0.1.6

COPY addon_launcher.py /usr/local/bin/house-brain-addon
RUN chmod 755 /usr/local/bin/house-brain-addon

ENTRYPOINT ["/usr/local/bin/house-brain-addon"]

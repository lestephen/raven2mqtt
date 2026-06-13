# Build the wheel in a throwaway stage, then install it into a slim runtime.
FROM python:3.12-slim AS build
WORKDIR /src
COPY . .
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /dist

FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/lestephen/raven2mqtt" \
      org.opencontainers.image.description="Rainforest RAVEn / EMU-2 serial-to-MQTT bridge for Home Assistant" \
      org.opencontainers.image.licenses="Apache-2.0"
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl
# Mount the TOML config at /config; optionally persist state at /data.
VOLUME ["/config", "/data"]
ENTRYPOINT ["raven2mqtt"]
CMD ["--config", "/config/raven2mqtt.toml", "run"]

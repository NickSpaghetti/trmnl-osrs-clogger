# OSRS Collection Log TRMNL plugin, served by the official trmnlp dev server
# (https://github.com/usetrmnl/trmnlp). This FROM line is the single source of the trmnlp version.
FROM trmnl/trmnlp:v0.34.1 AS base

WORKDIR /plugin
EXPOSE 4567
CMD ["serve", "--bind", "0.0.0.0"]

# Development: the project folder is mounted at /plugin at run time (make start),
# so edits under src/ reload the preview live.
FROM base AS development

# Production: the plugin is baked into the image and served as-is.
FROM base AS production
COPY .trmnlp.yml /plugin/.trmnlp.yml
COPY src /plugin/src
COPY tests /plugin/tests

PROJECT_NAME ?= trmnl-osrs-clog
IMAGE_OWNER ?= nickspaghetti/${PROJECT_NAME}
REGISTRY_URL = ghcr.io/${IMAGE_OWNER}
IMAGE_NAME ?= ${PROJECT_NAME}
RELEASE_TAG ?= "v0"
IMAGE_VERSION ?= local
IMAGE_FULL_NAME = "${REGISTRY_URL}/${IMAGE_NAME}"
DOCKER_BUILDX_FLAG_PLATFORM ?= linux/amd64
DOCKER_BUILDX_FLAG_OUTPUT ?= docker
CONTAINER_NAME ?= ${PROJECT_NAME}
PORT ?= 4567

# Build docker image by spec
# Parameters:
#	$1 - Docker build target (production, development)
#	$2 - Docker image tag (local, local-dev)
define build_image_by_spec
	@docker buildx create --use
	@docker buildx build \
		--target $1 \
		--tag $2 \
		--pull \
		--output=type=${DOCKER_BUILDX_FLAG_OUTPUT} \
		--platform ${DOCKER_BUILDX_FLAG_PLATFORM} \
		.
endef

.DEFAULT_GOAL := build

.PHONY: help remove build build-dev test which-image run shell pull push release start stop logs lint plugin-test publish zip

help:			## Show help menu
	@grep -E '^[a-zA-Z_\%-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

remove:		    ## Remove previously built Docker image
	@docker rmi ${IMAGE_FULL_NAME}:${IMAGE_VERSION}

build: 			## Build production Docker image
	@$(call build_image_by_spec,production,${IMAGE_FULL_NAME}:${IMAGE_VERSION})

build-dev:		## Build development Docker image
	@$(call build_image_by_spec,development,${IMAGE_FULL_NAME}:${IMAGE_VERSION}-dev)

test: 			## Run tests against the image
	@container-structure-test test --image ${IMAGE_FULL_NAME}:${IMAGE_VERSION} --config tests.yaml

which-image:	## Image identifier helper
	@echo ${IMAGE_FULL_NAME}:${IMAGE_VERSION}

run:			## Run the production plugin server on http://localhost:${PORT}
	@docker run --rm -p ${PORT}:4567 ${IMAGE_FULL_NAME}:${IMAGE_VERSION}

shell:			## Shell into the plugin container
	@docker run -it --rm --entrypoint /bin/bash ${IMAGE_FULL_NAME}:${IMAGE_VERSION}

pull:			## Pull image and mark as local
	docker pull ${IMAGE_FULL_NAME}:${IMAGE_VERSION}
	docker tag ${IMAGE_FULL_NAME}:${IMAGE_VERSION} ${IMAGE_FULL_NAME}:local

push:			## Push image to artifact registry
	@docker tag ${IMAGE_FULL_NAME}:local ${IMAGE_FULL_NAME}:${IMAGE_VERSION}
	@docker push ${IMAGE_FULL_NAME}:${IMAGE_VERSION}

release:		## Release Image to Registry
	@$(call build_image_by_spec,production,${IMAGE_FULL_NAME}:${RELEASE_TAG})

start: stop		## (Re)start the dev server with live reload on http://localhost:${PORT}
	@docker run -d \
		--name ${CONTAINER_NAME} \
		-p ${PORT}:4567 \
		-v "$(CURDIR):/plugin" \
		${IMAGE_FULL_NAME}:${IMAGE_VERSION}-dev
	@echo "Dev server running at http://localhost:${PORT}"

stop:			## Stop the dev server
	-@docker rm -f ${CONTAINER_NAME} >/dev/null 2>&1 || true

logs:			## Follow the dev server logs
	@docker logs -f ${CONTAINER_NAME}

lint:			## Run trmnlp lint against the source
	@docker run --rm -v "$(CURDIR):/plugin" ${IMAGE_FULL_NAME}:${IMAGE_VERSION}-dev lint

plugin-test:	## Run trmnlp plugin tests (writes report/)
	@docker run --rm -e CI -v "$(CURDIR):/plugin" ${IMAGE_FULL_NAME}:${IMAGE_VERSION}-dev test --report report

publish:		## Publish to an existing TRMNL plugin (needs TRMNL_API_KEY and TRMNL_PLUGIN_ID)
	@test -n "$$TRMNL_API_KEY" || (echo "TRMNL_API_KEY is not set" && exit 1)
	@test -n "$$TRMNL_PLUGIN_ID" || (echo "TRMNL_PLUGIN_ID is not set; without it trmnlp push creates a new plugin" && exit 1)
	@docker run --rm -e TRMNL_API_KEY -v "$(CURDIR):/plugin" ${IMAGE_FULL_NAME}:${IMAGE_VERSION}-dev push --force --id "$$TRMNL_PLUGIN_ID"

zip:			## Package src/ as a flat ZIP for TRMNL "Import new" (writes _build/${PROJECT_NAME}.zip)
	@mkdir -p _build
	@rm -f _build/${PROJECT_NAME}.zip
	@cd src && zip -q -X ../_build/${PROJECT_NAME}.zip settings.yml *.liquid transform.*
	@unzip -l _build/${PROJECT_NAME}.zip

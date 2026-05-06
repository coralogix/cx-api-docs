.PHONY: clean build generate-overviews test install install-dev

clean:
	rm -rf api-reference/v5

build:
	mintlify-scrape openapi-file openapi_v5.yaml openapi_v5.yaml -o api-reference/v5 \
	&& python3 generate_service_overviews.py \
	&& python3 build_navigation_file.py

generate-overviews:
	python3 generate_service_overviews.py

test:
	python3 -m pytest tests/ -v

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

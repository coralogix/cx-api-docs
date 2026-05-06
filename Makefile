.PHONY: clean build

clean:
	rm -rf api-reference/v5

build:
	mintlify-scrape openapi-file openapi_v5.yaml openapi_v5.yaml -o api-reference/v5 \
	&& python3 build_navigation_file.py

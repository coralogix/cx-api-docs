clean:
	rm -rf api-reference

build:
	mintlify-scrape openapi-file openapi_v3.yaml openapi_v3.yaml -o api-reference/v3 \
	&& mintlify-scrape openapi-file openapi_v4.yaml openapi_v4.yaml -o api-reference/v4 \
	&& mintlify-scrape openapi-file openapi_v5.yaml openapi_v5.yaml -o api-reference/v5 \
	&& python3 build_navigation_file.py

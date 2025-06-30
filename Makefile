build:
	mintlify-scrape openapi-file openapi_latest.yaml ../../openapi_latest.yaml -o api-reference/latest \
	&& mintlify-scrape openapi-file openapi_lts.yaml ../../openapi_lts.yaml -o api-reference/lts \
	&& ./place_overviews.sh \
	&& python build_navigation_file.py



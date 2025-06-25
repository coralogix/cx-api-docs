build:
	npx @mintlify/scraping@latest openapi-file openapi.yaml -o api-reference \
	&& ./place_overviews.sh \
	&& python build_navigation_file.py



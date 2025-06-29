#!/bin/bash

# Script to copy service overview files from service-overviews/ to api-reference/SERVICE_NAME/overview.mdx

# Check if service-overviews directory exists
if [ ! -d "service-overviews-latest" ]; then
    echo "Error: service-overviews directory not found"
    exit 1
fi

# Check if api-reference directory exists
if [ ! -d "api-reference/latest" ]; then
    echo "Error: api-reference/latest directory not found"
    exit 1
fi


echo "Processing service overview files..."

# Iterate through all files in service-overviews directory
for file in service-overviews-latest/*-overview.mdx; do
    # Extract the service name from the filename
    # Remove the path and the "-overview.mdx" suffix
    filename=$(basename "$file")
    service_name="${filename%-overview.mdx}"
    
    target_dir="api-reference/latest/$service_name"
    if [ ! -d "$target_dir" ]; then
        echo "$target_dir does not exist, exiting"
        exit 1
    fi
    
    # Define the target file path
    target_file="$target_dir/overview.mdx"
    
    
    # Copy the file
    echo "Copying $file to $target_file"
    cp "$file" "$target_file"
    
    if [ $? -eq 0 ]; then
        echo "Successfully copied $service_name-overview.mdx"
    else
        echo "Error copying $file"
    fi
done


if [ ! -d "service-overviews-lts" ]; then
    echo "Error: service-overviews-lts directory not found"
    exit 1
fi

# Check if api-reference directory exists
if [ ! -d "api-reference/lts" ]; then
    echo "Error: api-reference directory not found"
    exit 1
fi


echo "Processing service overview files..."

# Iterate through all files in service-overviews directory
for file in service-overviews-lts/*-overview.mdx; do
    # Extract the service name from the filename
    # Remove the path and the "-overview.mdx" suffix
    filename=$(basename "$file")
    service_name="${filename%-overview.mdx}"
    
    target_dir="api-reference/lts/$service_name"
    if [ ! -d "$target_dir" ]; then
        echo "$target_dir does not exist, exiting"
        exit 1
    fi
    
    # Define the target file path
    target_file="$target_dir/overview.mdx"
    
    
    # Copy the file
    echo "Copying $file to $target_file"
    cp "$file" "$target_file"
    
    if [ $? -eq 0 ]; then
        echo "Successfully copied $service_name-overview.mdx"
    else
        echo "Error copying $file"
    fi
done
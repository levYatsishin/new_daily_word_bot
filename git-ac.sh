#!/bin/bash

# Check if a commit message was provided
if [ -z "$1" ]; then
    echo "Please provide a commit message"
    echo "Usage: ./git-ac.sh 'your commit message'"
    exit 1
fi

# Add all changes and commit
git add .
git commit -m "$1" 
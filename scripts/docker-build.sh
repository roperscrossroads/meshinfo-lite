#!/usr/bin/env bash

# build

# set version from args if not, exit
#if [ -z "$1" ]
#  then
#    echo "No version supplied (e.g. 1.0.0)"
#    exit 1
#fi

REPO=dadecoza/meshinfo
# VERSION=$1
VERSION=latest

docker build -t $REPO:$VERSION --platform=linux/amd64 .

#!/bin/bash
# This script requires docker >= 1.12
# You need to build the image with: docker build -t worker .

exec &> /dev/null

# Get absolute path for nyuki lib.
pushd ../../nyuki/
LIB_SRC=`pwd`
LIB_DEST=/usr/lib/python3.5/site-packages/nyuki
popd

# Clean swarm services and config.
docker service rm worker mongo redis mosquitto
docker network rm workspace
docker swarm leave --force

# Init swarm services
docker swarm init
docker network create --driver overlay workspace
sleep 1

# Create services
docker service create --name mongo --replicas 1 --network workspace mongo:3.4
docker service create --name redis --replicas 1 --network workspace redis:3.2
docker service create --name mosquitto --replicas 1 --network workspace toke/mosquitto

docker service create --name worker --replicas 5 --network workspace \
    --mount type=bind,source=${LIB_SRC},destination=${LIB_DEST},ro=1 \
    --mount type=bind,source=$(pwd),destination=/home/,ro=0 \
    worker python3 worker.py
sleep 3

exec &>/dev/tty
docker service ps worker
docker service logs --follow worker

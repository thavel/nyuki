#!/bin/bash
# This script requires docker >= 1.12
# You need to build the image with: docker build -t worker .

exec &> /dev/null

# Get absolute path for nyuki lib.
pushd ../../nyuki/
WORKSPACE=`pwd`
MOUNT=/usr/lib/python3.5/site-packages/nyuki
popd

# Clean swarm services and config.
docker service rm worker
docker swarm leave --force
docker swarm init
docker network create --driver overlay workspace
sleep 1

# Create service
docker service create --name worker --replicas 3 --network workspace \
    --mount type=bind,source=${WORKSPACE},destination=${MOUNT},ro=1 \
    worker sleep 36000
sleep 3
SHA=`docker ps -q -f name=worker.1`

exec &>/dev/tty
docker service ps worker

# Access the container
echo -e "\nworker.1 container: ${SHA}\n"
docker exec -it ${SHA} ash

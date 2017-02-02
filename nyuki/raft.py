import json
import math
import socket
import logging
import asyncio
import aiohttp
from enum import Enum
from uuid import uuid4
from random import uniform

from nyuki.services import Service
from nyuki.api import Response, resource


log = logging.getLogger(__name__)


class State(Enum):
    UNKNOWN = 'unknown'
    FOLLOWER = 'follower'
    CANDIDATE = 'candidate'
    LEADER = 'leader'


@resource('/raft', ['v1'], 'application/json')
class ApiRaft:
    """
    This interface enables communication between members of a Raft cluster.
    """
    async def put(self, request):
        """
        Raft candidate request.
        """
        proto = self.nyuki.raft
        # If this instance has already voted for another one
        if proto.voted_for:
            return Response(
                status=403,
                body={'voted': proto.voted_for, 'instance': proto.uid}
            )

        # Local variables
        data = await request.json()
        proto.voted_for = data['candidate']
        proto.term = data['term']

        # Reset the timer
        proto.set_timer(proto.candidate)
        return Response(status=200, body={'instance': proto.uid})

    async def post(self, request):
        """
        Heartbeat endpoint.
        """
        proto = self.nyuki.raft
        # Local variables
        proto.state = State.FOLLOWER
        proto.votes = 0
        proto.voted_for = None

        # Reset the timer
        proto.set_timer(proto.candidate)
        return Response(status=200, body={'instance': proto.uid})


class RaftProtocol(Service):
    """
    Leader election based on Raft distributed algorithm.
    Paper: https://raft.github.io/raft.pdf
    """

    HEARTBEAT = 1.0
    TIMEOUT = (2.0, 3.5)

    def __init__(self, nyuki):
        self.service = nyuki.config['service']
        self.loop = nyuki.loop or asyncio.get_event_loop()
        self.uid = str(uuid4())[:8]
        self.ipv4 = socket.gethostbyname(socket.gethostname())

        self.cluster = {}
        self.suspicious = set()
        self.timer = None
        self.state = State.UNKNOWN
        self.term = -1
        self.votes = -1
        self.voted_for = None
        self.majority = math.inf

    def configure(self, *args, **kwargs):
        pass

    def set_timer(self, cb, factor=1):
        """
        Set or reset a unique timer.
        """
        if self.timer:
            self.timer.cancel()
        self.timer = self.loop.call_later(
            uniform(*self.TIMEOUT) * factor, asyncio.ensure_future, cb()
        )

    @staticmethod
    async def request(ipv4, method, data=None):
        """
        Utility method to perform HTTP requests, Raft-specific, to an instance.
        """
        request = {
            'url': 'http://{host}:5558/v1/raft'.format(host=ipv4),
            'headers': {'Content-Type': 'application/json'},
            'data': json.dumps(data or {})
        }
        try:
            async with aiohttp.ClientSession() as session:
                http_method = getattr(session, method)
                async with http_method(**request) as resp:
                    if resp.status != 200:
                        return
                    return await resp.json()
        except aiohttp.errors.ClientOSError:
            return

    async def start(self, *args, **kwargs):
        """
        Starts the protocol as a follower instance.
        """
        self.state = State.FOLLOWER
        self.term = 0
        self.votes = 0
        # Won't bootstrap the timer here to avoid any unwanted early election

    async def stop(self, *args, **kwargs):
        """
        Stops the protocol by cancelling the current timer.
        """
        self.state = State.FOLLOWER
        if self.timer:
            self.timer.cancel()

    async def discovery_handler(self, addresses):
        """
        The discovery service provides updates periodically.
        """
        cluster = {ipv4: self.cluster.get(ipv4) for ipv4 in addresses}
        if self.ipv4 in cluster:
            del cluster[self.ipv4]
        else:
            log.warning("This instance isn't part of the discovery results")

        # Check differences
        added = set(cluster.keys()) - set(self.cluster.keys())
        self.suspicious = set(self.cluster.keys()) - set(cluster.keys())
        self.cluster = cluster

        if self.state is State.LEADER:
            # Schedule HB for new workers
            for ipv4 in added:
                asyncio.ensure_future(self.heartbeat(ipv4))
        elif self.state is State.FOLLOWER and not self.timer:
            # The protocol has started but the timer needs to be bootstraped
            # Initial factor for the timer is higher (discovery reasons)
            self.set_timer(self.candidate, 3)

    async def candidate(self):
        """
        Election timer went out, this instance considers itself as a candidate.
        """
        cluster_size = len(self.cluster) + 1

        # Promote itself as leader if alone
        if cluster_size == 1:
            await self.promote()
            return

        # Local variables
        self.state = State.CANDIDATE
        self.term += 1
        self.votes = 1
        self.voted_for = self.uid
        self.majority = int(math.floor(cluster_size / 2) + 1)

        # Init the timer, retry vote if timeout
        log.debug("Instance is candidate (requires %d votes)", self.majority)
        self.set_timer(self.candidate)

        # Start the election
        for ipv4 in self.cluster:
            asyncio.ensure_future(self.request_vote(ipv4, self.term))

    async def promote(self):
        """
        Promote this instance to the rank of leader.
        """
        log.info("Leader elected of the service '%s'", self.service)

        # Local variables
        if self.timer:
            self.timer.cancel()
        self.state = State.LEADER
        self.votes = 0
        self.voted_for = None

        # Sending heartbeats to the cluster
        for ipv4 in self.cluster:
            asyncio.ensure_future(self.heartbeat(ipv4))

    async def request_vote(self, ipv4, term):
        """
        Request a vote from an instance.
        """
        vote = await self.request(ipv4, 'put', {
            'candidate': self.uid, 'term': term
        })
        if (
            # Won't count negative feedbacks
            not vote or
            # Ignore the vote if the election is over
            self.term != term or self.loop.time() >= self.timer._when or
            # Not in a candidate anymore
            self.state is not State.CANDIDATE
        ):
            return

        # Count vote
        self.cluster[ipv4] = vote['instance']
        self.votes += 1

        # The instance becomes a leader
        if self.votes >= self.majority:
            await self.promote()

    async def heartbeat(self, ipv4):
        """
        Send a heartbeat to reset instance's timer.
        """
        if (
            # Won't send HB if the instance is not the leader anymore
            self.state is not State.LEADER or
            # If an instance disappears from the membership, stop sending HB
            ipv4 in self.suspicious or
            # Won't send HB if he instances is not in the cluster
            ipv4 not in self.cluster
        ):
            return

        # Schedule the next HB
        self.loop.call_later(
            self.HEARTBEAT, asyncio.ensure_future, self.heartbeat(ipv4)
        )
        await self.request(ipv4, 'post', {'leader': self.uid})

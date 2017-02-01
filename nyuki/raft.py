import json
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
        proto.term += 1

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
        proto.voted_for = None

        # Reset the timer
        proto.set_timer(proto.candidate)
        return Response(status=200, body={'instance': proto.uid})


class RaftProtocol(Service):
    """
    Leader election based on Raft distributed algorithm.
    Paper: https://raft.github.io/raft.pdf
    """

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

    def configure(self, *args, **kwargs):
        pass

    def set_timer(self, cb):
        """
        Set or reset a unique timer.
        """
        if self.timer:
            self.timer.cancel()
        self.timer = self.loop.call_later(
            uniform(5.0, 10.0), asyncio.ensure_future, cb()
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
        self.state = State.FOLLOWER
        self.term = 0
        self.votes = 0
        self.set_timer(self.candidate)

    async def stop(self, *args, **kwargs):
        if self.timer:
            self.timer.cancel()

    async def discovery_handler(self, addresses):
        """
        The discovery service provides updates periodically.
        """
        cluster = {ipv4: self.cluster.get(ipv4) for ipv4 in addresses}
        del cluster[self.ipv4]

        # Check differences
        added = set(cluster.keys()) - set(self.cluster.keys())
        self.suspicious = set(self.cluster.keys()) - set(cluster.keys())
        self.cluster = cluster

        if self.state is State.LEADER:
            # Schedule HB for new workers
            for ipv4 in added:
                asyncio.ensure_future(self.heartbeat(ipv4))

    async def candidate(self):
        """
        Election timer went out, this instance considers itself as a candidate.
        """
        # Local variables
        self.state = State.CANDIDATE
        self.voted_for = self.uid
        self.term += 1
        self.votes += 1

        # Init the timer, retry vote if timeout
        self.set_timer(self.candidate)

        # Promote itself as leader if alone
        if len(self.cluster) < 1:
            await self.promote()
            return

        # Start the election
        for ipv4 in self.cluster:
            asyncio.ensure_future(self.request_vote(ipv4, self.term))

    async def promote(self):
        """
        Promote this instance to the rank of leader.
        """
        log.info("Leader elected of the service '{}'".format(self.service))
        self.timer.cancel()
        self.state = State.LEADER

        # Sending heartbeats to the cluster
        for ipv4 in self.cluster:
            asyncio.ensure_future(self.heartbeat(ipv4))

    async def request_vote(self, ipv4, term):
        """
        Request a vote from an instance.
        """
        vote = await self.request(ipv4, 'put', {'candidate': self.uid})
        if not vote:
            # Won't count negative feedbacks
            return
        if self.term != term or self.loop.time() >= self.timer._when:
            # Ignore the vote if the election is over
            return
        if self.state is State.LEADER:
            # Already a leader
            return

        # Count vote
        self.cluster[ipv4] = vote['instance']
        self.votes += 1

        # The node becomes a leader
        if self.votes >= len(self.cluster)/2 + 1:
            await self.promote()

    async def heartbeat(self, ipv4):
        """
        Send a heartbeat to reset instance's timer.
        """
        if self.state is not State.LEADER:
            # Won't send HB if the node is not the leader anymore
            return
        if ipv4 in self.suspicious:
            # If a node disappears from the membership list, stop sending HB
            self.suspicious.remove(ipv4)
            return
        if ipv4 not in self.cluster:
            # Won't send HB if he instances is not in the cluster
            return

        # Schedule the next HB
        self.loop.call_later(5, asyncio.ensure_future, self.heartbeat(ipv4))
        await self.request(ipv4, 'post', {'leader': self.uid})

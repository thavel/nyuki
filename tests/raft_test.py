import json
from asynctest import TestCase, Mock, patch, CoroutineMock
from nose.tools import eq_, assert_in, assert_not_equal, assert_not_in

from nyuki.raft import ApiRaft, RaftProtocol, State


def from_context(params={}):
    nyuki = Mock()
    nyuki.config = {'service': 'test'}
    nyuki.raft = RaftProtocol(nyuki)
    nyuki.raft.ipv4 = '10.50.0.1'
    for key, value in params.items():
        setattr(nyuki.raft, key, value)
    return nyuki


class Request(object):

    def __init__(self, content):
        self._content = content

    async def json(self):
        return self._content


class TestRaftApi(TestCase):

    def setUp(self):
        self.api = ApiRaft()

    async def test_001a_put(self):
        """
        000002 ask for 000001's vote during term 10
        """
        self.api.nyuki = from_context({
            'uid': '000001'
        })
        request = Request({'candidate': '000002', 'term': 10})
        response = await self.api.put(request)
        eq_(response.status, 200)
        assert_in('instance', json.loads(response.text))
        assert_not_equal(self.api.nyuki.raft.timer, None)

    async def test_001b_put(self):
        """
        000002 has already voted for 000003 in term 10
        """
        self.api.nyuki = from_context({
            'uid': '000001',
            'voted_for': '000003',
        })
        request = Request({'candidate': '000002', 'term': 11})
        response = await self.api.put(request)
        eq_(response.status, 403)
        data = json.loads(response.text)
        assert_in('instance', data)
        eq_(data['voted'], '000003')
        eq_(self.api.nyuki.raft.timer, None)

    async def test_002_post(self):
        """
        000002 sends a heartbeat to 000001
        """
        self.api.nyuki = from_context({
            'uid': '000001'
        })
        request = Request({'candidate': '000002', 'term': 12})
        response = await self.api.post(request)
        eq_(response.status, 200)
        eq_(self.api.nyuki.raft.state, State.FOLLOWER)
        assert_not_equal(self.api.nyuki.raft.timer, None)


class TestRaftProtocol(TestCase):

    @patch('nyuki.raft.RaftProtocol.heartbeat')
    async def test_001a_discovery(self, hb_mock):
        """
        Discovery handler called before the protocol has started
        """
        raft = from_context().raft
        await raft.discovery_handler(['10.50.0.1', '10.50.0.2', '10.50.0.3'])
        assert_not_in('10.50.0.1', raft.cluster)
        eq_(raft.timer, None)
        eq_(hb_mock.call_count, 0)

    @patch('nyuki.raft.RaftProtocol.heartbeat')
    async def test_001b_discovery(self, hb_mock):
        """
        Discovery handler called with additional and suspicious instances
        """
        raft = from_context({
            'cluster': {'10.50.0.2': '000002'}
        }).raft
        await raft.start()
        raft.state = State.LEADER

        await raft.discovery_handler(['10.50.0.1', '10.50.0.3'])
        assert_in('10.50.0.2', raft.suspicious)
        assert_in('10.50.0.3', raft.cluster)
        eq_(hb_mock.call_count, 1)

    @patch('nyuki.raft.RaftProtocol.request_vote')
    async def test_002a_candidate(self, vote_mock):
        """
        Init or timer wen't out, the instance is candidate and alone
        """
        raft = from_context({
            'state': State.FOLLOWER,
            'cluster': {}
        }).raft
        await raft.candidate()
        eq_(raft.state, State.LEADER)
        eq_(vote_mock.call_count, 0)

    @patch('nyuki.raft.RaftProtocol.request_vote')
    async def test_002b_candidate(self, vote_mock):
        """
        Init or timer wen't out, the instance is candidate
        """
        raft = from_context({
            'state': State.FOLLOWER,
            'cluster': {'10.50.0.2': '000002'}
        }).raft
        await raft.candidate()
        eq_(raft.state, State.CANDIDATE)
        eq_(vote_mock.call_count, 1)

    async def test_003a_vote(self):
        """
        Get a vote from an instance
        """
        raft = from_context({
            'uid': '000001',
            'state': State.CANDIDATE,
            'term': 13,
            'votes': 1,
            'majority': 5
        }).raft
        raft.loop = Mock()
        raft.loop.time = lambda: 1
        raft.timer = Mock()
        raft.timer._when = 2

        coro = 'nyuki.raft.RaftProtocol.request'
        with patch(coro, new=CoroutineMock()) as request_mock:
            request_mock.return_value = {'instance': '10.50.0.2'}
            await raft.request_vote('10.50.0.2', 13)
            assert_not_equal(raft.state, State.LEADER)
            eq_(raft.votes, 2)

    async def test_003b_vote(self):
        """
        Get a vote from an instance and reach the majority
        """
        raft = from_context({
            'uid': '000001',
            'state': State.CANDIDATE,
            'term': 13,
            'votes': 1,
            'majority': 2
        }).raft
        raft.loop = Mock()
        raft.loop.time = lambda: 1
        raft.timer = Mock()
        raft.timer._when = 2

        coro = 'nyuki.raft.RaftProtocol.request'
        with patch(coro, new=CoroutineMock()) as request_mock:
            request_mock.return_value = {'instance': '10.50.0.2'}
            await raft.request_vote('10.50.0.2', 13)
            eq_(raft.state, State.LEADER)

# -*- coding: utf-8 -*-

import time
import socket

import msgpack
import pytest
from mock import MagicMock, patch, call

from pyfluent import client


def test_geometric_sequence():
    gs = client.geometric_sequence()
    assert [next(gs) for x in range(8)] == [
        1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0
    ]
    gs = client.geometric_sequence(2.0, 1.5, 60.0)
    assert [next(gs) for x in range(8)] == [
        2.0, 3.0, 4.5, 6.75, 10.125, 15.1875, 22.78125, 34.171875
    ]


class TestFluentSender(object):
    def pytest_funcarg__sender(self, request):
        return client.FluentSender('test')

    def test_init(self, sender):
        assert sender.default_tag == 'test'
        assert sender.host == 'localhost'
        assert sender.port == 24224
        assert sender.timeout == 1
        assert sender._retry_time == 0
        assert isinstance(sender.packer, msgpack.Packer)

    def test_make_socket(self, sender):
        with patch('socket.socket'):
            sock = sender._make_socket()
            assert sock.mock_calls == [
                call.settimeout(sender.timeout),
                call.connect((sender.host, sender.port))
            ]

    def test_create_socket(self, sender):
        sender._retry_time = time.time() + 1000
        sender._create_socket()
        assert sender._sock == None
        sender._retry_time = time.time()
        with patch('socket.socket'):
            sender._create_socket()
            assert sender._sock is not None
            assert sender._retry_time == 0
            assert next(sender._wait_time) == 1.0

    def test_create_socket_error(self, sender):
        with patch('socket.socket') as mock:
            mock.side_effect = socket.error
            now = time.time()
            sender._create_socket()
            assert sender._sock is None
            assert now < sender._retry_time < now + 2.0
            assert next(sender._wait_time) == 2.0

    def test_get_socket(self, sender):
        with patch('socket.socket'):
            assert sender._sock is None
            sock1 = sender.socket
            assert sock1 is not None
            assert sender._sock is sock1
            sock2 = sender.socket
            assert sock1 is sock2

    def test_close(self, sender):
        sender.close()
        assert sender._retry_time == 0
        assert next(sender._wait_time) == 1.0
        mock = sender._sock = MagicMock(spec=socket.socket)
        sender.close()
        assert mock.method_calls == [call.close()]
        assert sender._sock == None
        assert sender._retry_time == 0
        assert next(sender._wait_time) == 1.0

    def test_serialize_default_args(self, sender):
        now = time.time()
        r1 = sender.serialize('test data')
        r2 = sender.serialize({'message': 'test'})
        r1 = msgpack.unpackb(r1)
        r2 = msgpack.unpackb(r2)
        assert r1[0] == r2[0] == sender.default_tag
        assert now < r1[1] <= r2[1] < now + 2
        assert r1[2] == {'data': 'test data'}
        assert r2[2] == {'message': 'test'}

    def test_serialize(self, sender):
        data = {'string': 'test', 'number': 10}
        tag = 'pyfluent.test'
        timestamp = time.time()
        r = sender.serialize(data, tag, timestamp)
        assert msgpack.unpackb(r) == (tag, timestamp, data)

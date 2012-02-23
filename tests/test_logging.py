# -*- coding: utf-8 -*-

import os
import logging
import socket

import pytest
from mock import Mock
import msgpack

import pyfluent.logging

_RECORD_CREATED = 1329904180.791739


def pytest_funcarg__record(request):
    record = logging.LogRecord(
        'root', logging.INFO, '/path/to/source.py',
        '10', 'message %d', (1, ), None, 'func_name'
    )
    record.created = _RECORD_CREATED
    return record


def pytest_funcarg__logger(request):
    return LogRecordCapture()


class LogRecordCapture(object):
    def __init__(self):
        handler = logging.Handler()
        handler.setLevel(logging.DEBUG)
        self.mock = Mock(spec=handler.emit)
        handler.emit = self.mock
        self.logger = logging.getLogger('pytest.fluent')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

    def __getattr__(self, key):
        if hasattr(self.logger, key):
            return getattr(self.logger, key)
        super(LogRecordCapture, self).__getattr__(key)

    def get(self):
        return self.mock.call_args[0][0]


class TestFluentHandler(object):
    @staticmethod
    def pytest_generate_tests(metafunc):
        body = {'message': 'message 1'}
        handler_without_tag = pyfluent.logging.FluentHandler()
        handler_with_tag = pyfluent.logging.FluentHandler(tag='test')
        metafunc.parametrize(('handler', 'expected'), [
            (handler_without_tag, ('info', _RECORD_CREATED, body)),
            (handler_with_tag, ('test.info', _RECORD_CREATED, body)),
        ])

    def test_packing(self, handler, record, expected):
        data = handler.makePickle(record)
        assert msgpack.unpackb(data) == expected


class TestFluentFormatter(object):
    hostname = socket.gethostname()

    @pytest.mark.parametrize(('key', 'value', 'expected'), [
        ('name', 'root', ('name', 'root')),
        ('levelname', 'INFO', ('levelname', 'info'))
    ])
    def test_prepare(self, key, value, expected):
        fmt = pyfluent.logging.FluentFormatter()
        assert fmt.prepare(key, value) == expected

    def test_format(self, record):
        fmt = pyfluent.logging.FluentFormatter()
        assert fmt.format(record) == {
            'message': 'message 1',
            'hostname': self.hostname,
            'filename': 'source.py',
            'name': 'root',
            'levelname': 'info',
            'lineno': '10',
            'funcName': 'func_name',
            'exc_text': None,
            'module': 'source',
            'pathname': '/path/to/source.py',
            'process': os.getpid(),
            'processName': 'MainProcess',
            'threadName': 'MainThread'
        }

    def test_format_with_specify_format(self, logger):
        msg = '%(asctime)s %(levelname)s %(message)s'
        fmt = pyfluent.logging.FluentFormatter(msg)
        logger.info('message for test %d', 1)
        data = fmt.format(logger.get())
        assert data['name'] == 'pytest.fluent'
        assert data['message'].endswith(' INFO message for test 1')
        assert 'asctime' not in data

    def test_format_with_extra(self, logger):
        fmt = pyfluent.logging.FluentFormatter()
        logger.info('message for test', extra={'additional': 'information'})
        data = fmt.format(logger.get())
        assert data['name'] == 'pytest.fluent'
        assert data['message'] == 'message for test'
        assert data['additional'] == 'information'

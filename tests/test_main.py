# -*- coding: utf-8 -*-
# from pytest import raises

# The parametrize function is generated, so this doesn't work:
#
#     from pytest.mark import parametrize
#
import pytest
parametrize = pytest.mark.parametrize


class TestMain(object):
    logfile = open("/tmp/test-btsbots.log", 'a')

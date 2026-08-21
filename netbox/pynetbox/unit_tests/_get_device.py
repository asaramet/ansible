#!/usr/bin/env python3

'''
Unit Tests for _get_device
'''
from unittest.mock import MagicMock
import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pynetbox_functions import _get_device

@pytest.fixture
def mock_nb_session():
    """Mock NetBox API session."""
    return MagicMock()


def test_get_device_success(mock_nb_session):
    """Test returning a device when a valid match is found."""
    mock_device = MagicMock()
    mock_device.name = "switch-01"
    mock_nb_session.dcim.devices.get.return_value = mock_device

    result = _get_device(mock_nb_session, "switch-01")

    assert result == mock_device
    mock_nb_session.dcim.devices.get.assert_called_once_with(name="switch-01")


def test_get_device_empty_name(mock_nb_session):
    """Test empty/None input returns None without making an API call."""
    assert _get_device(mock_nb_session, "") is None
    assert _get_device(mock_nb_session, None) is None
    mock_nb_session.dcim.devices.get.assert_not_called()


def test_get_device_not_found(mock_nb_session):
    """Test returning None when no matching device exists."""
    mock_nb_session.dcim.devices.get.return_value = None

    result = _get_device(mock_nb_session, "nonexistent-device")

    assert result is None


def test_get_device_multiple_found_value_error(mock_nb_session):
    """Test handling ValueError when duplicate device names exist."""
    mock_nb_session.dcim.devices.get.side_effect = ValueError(
        "More than one result returned"
    )

    result = _get_device(mock_nb_session, "duplicate-switch")

    assert result is None


def test_get_device_unexpected_exception(mock_nb_session):
    """Test catching unexpected network/API errors gracefully."""
    mock_nb_session.dcim.devices.get.side_effect = RuntimeError(
        "Connection refused"
    )

    result = _get_device(mock_nb_session, "switch-01")

    assert result is None
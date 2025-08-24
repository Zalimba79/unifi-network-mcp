"""Tests for DeviceManager with switch port management."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.managers.device_manager import DeviceManager


@pytest.fixture
def mock_connection():
    """Create a mock connection manager."""
    connection = MagicMock()
    connection.ensure_connected = AsyncMock(return_value=True)
    connection.request = AsyncMock()
    connection._invalidate_cache = MagicMock()
    return connection


@pytest.fixture
def device_manager(mock_connection):
    """Create a DeviceManager instance with mock connection."""
    return DeviceManager(mock_connection)


@pytest.mark.asyncio
async def test_get_device_port_overrides(device_manager):
    """Test getting port overrides for a device."""
    # Setup mock device
    mock_device = MagicMock()
    mock_device.raw = {
        'port_overrides': [
            {'port_idx': 0, 'name': 'Port 1', 'forward': 'disabled'},
            {'port_idx': 1, 'name': 'Port 2', 'poe_mode': 'auto'}
        ]
    }
    
    # Mock get_device_details
    device_manager.get_device_details = AsyncMock(return_value=mock_device)
    
    # Test
    overrides = await device_manager.get_device_port_overrides('aa:bb:cc:dd:ee:ff')
    
    assert overrides is not None
    assert len(overrides) == 2
    assert overrides[0]['port_idx'] == 0
    assert overrides[0]['forward'] == 'disabled'
    assert overrides[1]['port_idx'] == 1
    assert overrides[1]['poe_mode'] == 'auto'


@pytest.mark.asyncio
async def test_toggle_switch_port_disable(device_manager, mock_connection):
    """Test disabling a switch port."""
    # Setup mock
    device_manager.get_device_port_overrides = AsyncMock(return_value=[])
    device_manager.update_device_port_overrides = AsyncMock(return_value=True)
    
    # Test disabling port
    result = await device_manager.toggle_switch_port('aa:bb:cc:dd:ee:ff', 0, False)
    
    assert result is True
    # Check that update was called with disabled forward
    call_args = device_manager.update_device_port_overrides.call_args[0]
    assert call_args[0] == 'aa:bb:cc:dd:ee:ff'
    assert call_args[1][0]['port_idx'] == 0
    assert call_args[1][0]['forward'] == 'disabled'


@pytest.mark.asyncio
async def test_toggle_switch_port_enable(device_manager, mock_connection):
    """Test enabling a switch port."""
    # Setup mock with disabled port
    existing_overrides = [{'port_idx': 0, 'forward': 'disabled'}]
    device_manager.get_device_port_overrides = AsyncMock(return_value=existing_overrides)
    device_manager.update_device_port_overrides = AsyncMock(return_value=True)
    
    # Test enabling port
    result = await device_manager.toggle_switch_port('aa:bb:cc:dd:ee:ff', 0, True)
    
    assert result is True
    # Check that update was called without forward key (enabled)
    call_args = device_manager.update_device_port_overrides.call_args[0]
    assert call_args[0] == 'aa:bb:cc:dd:ee:ff'
    assert call_args[1][0]['port_idx'] == 0
    assert 'forward' not in call_args[1][0]


@pytest.mark.asyncio
async def test_set_port_poe_mode(device_manager, mock_connection):
    """Test setting PoE mode for a port."""
    # Setup mock
    device_manager.get_device_port_overrides = AsyncMock(return_value=[])
    device_manager.update_device_port_overrides = AsyncMock(return_value=True)
    
    # Test setting PoE mode
    result = await device_manager.set_port_poe_mode('aa:bb:cc:dd:ee:ff', 2, 'auto')
    
    assert result is True
    # Check that update was called with PoE mode
    call_args = device_manager.update_device_port_overrides.call_args[0]
    assert call_args[0] == 'aa:bb:cc:dd:ee:ff'
    assert call_args[1][0]['port_idx'] == 2
    assert call_args[1][0]['poe_mode'] == 'auto'


@pytest.mark.asyncio
async def test_set_port_profile(device_manager, mock_connection):
    """Test setting port profile."""
    # Setup mock
    device_manager.get_device_port_overrides = AsyncMock(return_value=[])
    device_manager.update_device_port_overrides = AsyncMock(return_value=True)
    
    # Test setting port profile
    result = await device_manager.set_port_profile('aa:bb:cc:dd:ee:ff', 3, 'profile_123')
    
    assert result is True
    # Check that update was called with port profile
    call_args = device_manager.update_device_port_overrides.call_args[0]
    assert call_args[0] == 'aa:bb:cc:dd:ee:ff'
    assert call_args[1][0]['port_idx'] == 3
    assert call_args[1][0]['portconf_id'] == 'profile_123'


@pytest.mark.asyncio
async def test_set_port_name(device_manager, mock_connection):
    """Test setting custom port name."""
    # Setup mock
    device_manager.get_device_port_overrides = AsyncMock(return_value=[])
    device_manager.update_device_port_overrides = AsyncMock(return_value=True)
    
    # Test setting port name
    result = await device_manager.set_port_name('aa:bb:cc:dd:ee:ff', 4, 'Server Room')
    
    assert result is True
    # Check that update was called with port name
    call_args = device_manager.update_device_port_overrides.call_args[0]
    assert call_args[0] == 'aa:bb:cc:dd:ee:ff'
    assert call_args[1][0]['port_idx'] == 4
    assert call_args[1][0]['name'] == 'Server Room'


@pytest.mark.asyncio
async def test_get_port_profiles(device_manager, mock_connection):
    """Test getting available port profiles."""
    # Setup mock response
    mock_profiles = [
        {'_id': 'prof1', 'name': 'All VLANs'},
        {'_id': 'prof2', 'name': 'Guest Network'}
    ]
    mock_connection.request.return_value = mock_profiles
    
    # Test
    profiles = await device_manager.get_port_profiles()
    
    assert len(profiles) == 2
    assert profiles[0]['_id'] == 'prof1'
    assert profiles[0]['name'] == 'All VLANs'
    assert profiles[1]['_id'] == 'prof2'
    assert profiles[1]['name'] == 'Guest Network'
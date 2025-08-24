"""Tests for DHCP Manager and related tools."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.managers.dhcp_manager import DHCPManager
from src.validators import validate_mac_address, validate_ip_address


class TestValidators:
    """Test validation functions."""
    
    def test_validate_mac_address(self):
        """Test MAC address validation."""
        # Valid MAC addresses
        assert validate_mac_address("aa:bb:cc:dd:ee:ff") is True
        assert validate_mac_address("AA:BB:CC:DD:EE:FF") is True
        assert validate_mac_address("aa-bb-cc-dd-ee-ff") is True
        assert validate_mac_address("aabb.ccdd.eeff") is True
        assert validate_mac_address("aabbccddeeff") is True
        
        # Invalid MAC addresses
        assert validate_mac_address("") is False
        assert validate_mac_address("aa:bb:cc:dd:ee") is False  # Too short
        assert validate_mac_address("aa:bb:cc:dd:ee:ff:gg") is False  # Too long
        assert validate_mac_address("aa:bb:cc:dd:ee:gg") is False  # Invalid hex
        assert validate_mac_address("not-a-mac") is False
    
    def test_validate_ip_address(self):
        """Test IP address validation."""
        # Valid IPv4 addresses
        assert validate_ip_address("192.168.1.1") is True
        assert validate_ip_address("10.0.0.1") is True
        assert validate_ip_address("172.16.0.1") is True
        assert validate_ip_address("8.8.8.8") is True
        
        # Valid IPv6 addresses
        assert validate_ip_address("2001:db8::1") is True
        assert validate_ip_address("fe80::1") is True
        
        # Invalid IP addresses
        assert validate_ip_address("") is False
        assert validate_ip_address("192.168.1.256") is False  # Out of range
        assert validate_ip_address("192.168.1") is False  # Incomplete
        assert validate_ip_address("not-an-ip") is False


@pytest.fixture
def mock_connection():
    """Create a mock connection manager."""
    connection = MagicMock()
    connection.ensure_connected = AsyncMock(return_value=True)
    connection.controller = MagicMock()
    connection.controller.request = AsyncMock()
    connection._invalidate_cache = MagicMock()
    return connection


@pytest.fixture
def dhcp_manager(mock_connection):
    """Create a DHCPManager instance with mock connection."""
    return DHCPManager(mock_connection)


@pytest.mark.asyncio
async def test_list_dhcp_reservations(dhcp_manager, mock_connection):
    """Test listing DHCP reservations."""
    # Setup mock clients
    mock_client1 = MagicMock()
    mock_client1.id = "client1"
    mock_client1.mac = "aa:bb:cc:dd:ee:ff"
    mock_client1.use_fixedip = True
    mock_client1.fixed_ip = "192.168.1.100"
    mock_client1.network_id = "network1"
    mock_client1.name = "Test Device"
    
    mock_client2 = MagicMock()
    mock_client2.id = "client2"
    mock_client2.mac = "11:22:33:44:55:66"
    mock_client2.use_fixedip = False  # No fixed IP
    
    mock_connection.controller.clients.values.return_value = [mock_client1, mock_client2]
    
    # Mock network info
    mock_connection.controller.request.return_value = [
        {
            '_id': 'network1',
            'name': 'LAN',
            'ip_subnet': '192.168.1.0/24'
        }
    ]
    
    # Test
    reservations = await dhcp_manager.list_dhcp_reservations()
    
    assert len(reservations) == 1
    assert reservations[0]['mac'] == "aa:bb:cc:dd:ee:ff"
    assert reservations[0]['fixed_ip'] == "192.168.1.100"
    assert reservations[0]['network_name'] == "LAN"


@pytest.mark.asyncio
async def test_set_client_fixed_ip(dhcp_manager, mock_connection):
    """Test setting a fixed IP for a client."""
    # Setup mock client
    mock_client = MagicMock()
    mock_client.id = "client1"
    mock_client.mac = "aa:bb:cc:dd:ee:ff"
    
    mock_connection.controller.clients.values.return_value = [mock_client]
    
    # Mock network info for auto-detection
    mock_connection.controller.request.return_value = [
        {
            '_id': 'network1',
            'name': 'LAN',
            'ip_subnet': '192.168.1.0/24'
        }
    ]
    
    # Test setting fixed IP
    result = await dhcp_manager.set_client_fixed_ip(
        "aa:bb:cc:dd:ee:ff",
        "192.168.1.100"
    )
    
    assert result is True
    
    # Verify the API call
    mock_connection.controller.request.assert_called()
    call_args = mock_connection.controller.request.call_args[0][0]
    assert call_args.method == "put"
    assert "/rest/user/client1" in call_args.path
    assert call_args.data['use_fixedip'] is True
    assert call_args.data['fixed_ip'] == "192.168.1.100"


@pytest.mark.asyncio
async def test_remove_client_fixed_ip(dhcp_manager, mock_connection):
    """Test removing fixed IP from a client."""
    # Setup mock client
    mock_client = MagicMock()
    mock_client.id = "client1"
    mock_client.mac = "aa:bb:cc:dd:ee:ff"
    
    mock_connection.controller.clients.values.return_value = [mock_client]
    
    # Test removing fixed IP
    result = await dhcp_manager.remove_client_fixed_ip("aa:bb:cc:dd:ee:ff")
    
    assert result is True
    
    # Verify the API call
    mock_connection.controller.request.assert_called()
    call_args = mock_connection.controller.request.call_args[0][0]
    assert call_args.data['use_fixedip'] is False


@pytest.mark.asyncio
async def test_create_dhcp_reservation(dhcp_manager, mock_connection):
    """Test creating a new DHCP reservation."""
    # Mock network info for auto-detection
    mock_connection.controller.request.return_value = [
        {
            '_id': 'network1',
            'name': 'LAN',
            'ip_subnet': '192.168.1.0/24'
        }
    ]
    
    # Test creating reservation
    result = await dhcp_manager.create_dhcp_reservation(
        "aa:bb:cc:dd:ee:ff",
        "192.168.1.100",
        "New Device"
    )
    
    assert result is True
    
    # Verify the API call
    mock_connection.controller.request.assert_called()
    call_args = mock_connection.controller.request.call_args[0][0]
    assert call_args.method == "post"
    assert call_args.path == "/rest/user"
    assert call_args.data['mac'] == "aa:bb:cc:dd:ee:ff"
    assert call_args.data['use_fixedip'] is True
    assert call_args.data['fixed_ip'] == "192.168.1.100"
    assert call_args.data['name'] == "New Device"


@pytest.mark.asyncio
async def test_list_available_ips(dhcp_manager, mock_connection):
    """Test listing available IPs in a network."""
    # Mock network configuration
    mock_connection.controller.request.return_value = [
        {
            '_id': 'network1',
            'name': 'LAN',
            'ip_subnet': '192.168.1.0/24',
            'dhcpd_start': '192.168.1.100',
            'dhcpd_stop': '192.168.1.110'
        }
    ]
    
    # Mock existing reservations and active clients
    mock_client = MagicMock()
    mock_client.ip = "192.168.1.101"
    mock_connection.controller.clients.values.return_value = [mock_client]
    
    # Mock list_dhcp_reservations to return one reservation
    with patch.object(dhcp_manager, 'list_dhcp_reservations', return_value=[
        {'fixed_ip': '192.168.1.100'}
    ]):
        available = await dhcp_manager.list_available_ips('network1')
    
    # Should have IPs from .102 to .110 (9 IPs)
    # .100 is reserved, .101 is active
    assert len(available) == 9
    assert "192.168.1.102" in available
    assert "192.168.1.110" in available
    assert "192.168.1.100" not in available  # Reserved
    assert "192.168.1.101" not in available  # Active
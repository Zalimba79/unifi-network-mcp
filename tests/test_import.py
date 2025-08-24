"""Basic import tests for UniFi Network MCP."""

import pytest


def test_main_import():
    """Test that main module can be imported."""
    from src.main import main
    assert callable(main)


def test_runtime_import():
    """Test that runtime module can be imported."""
    from src.runtime import server, config
    assert server is not None
    assert config is not None


def test_managers_import():
    """Test that all managers can be imported."""
    from src.managers.connection_manager import ConnectionManager
    from src.managers.device_manager import DeviceManager
    from src.managers.network_manager import NetworkManager
    from src.managers.client_manager import ClientManager
    from src.managers.firewall_manager import FirewallManager
    from src.managers.system_manager import SystemManager
    from src.managers.vpn_manager import VPNManager
    from src.managers.qos_manager import QoSManager
    from src.managers.stats_manager import StatsManager
    
    # Just check they're importable
    assert ConnectionManager is not None
    assert DeviceManager is not None
    assert NetworkManager is not None
    assert ClientManager is not None
    assert FirewallManager is not None
    assert SystemManager is not None
    assert VPNManager is not None
    assert QoSManager is not None
    assert StatsManager is not None


def test_tools_import():
    """Test that tool modules can be imported."""
    import src.tools.clients
    import src.tools.devices
    import src.tools.network
    import src.tools.firewall
    import src.tools.port_forwards
    import src.tools.qos
    import src.tools.stats
    import src.tools.system
    import src.tools.traffic_routes
    import src.tools.vpn
    import src.tools.switch_ports
    
    # Just check they're importable
    assert src.tools.clients is not None
    assert src.tools.devices is not None
    assert src.tools.network is not None
    assert src.tools.firewall is not None
    assert src.tools.port_forwards is not None
    assert src.tools.qos is not None
    assert src.tools.stats is not None
    assert src.tools.system is not None
    assert src.tools.traffic_routes is not None
    assert src.tools.vpn is not None
    assert src.tools.switch_ports is not None


def test_config_structure():
    """Test that config has expected structure."""
    from src.runtime import config
    
    assert hasattr(config, 'unifi')
    assert hasattr(config, 'server')
    assert hasattr(config, 'permissions')
    
    # Check UniFi config
    assert 'host' in config.unifi
    assert 'username' in config.unifi
    assert 'password' in config.unifi
    
    # Check server config
    assert 'port' in config.server
    assert 'log_level' in config.server
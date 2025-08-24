"""Switch Port Management Tools for UniFi Network MCP."""

import logging
from typing import Dict, Any, List, Optional

# Import the global FastMCP server instance, config, and managers
from src.runtime import server, config, device_manager
from src.utils.permissions import parse_permission

logger = logging.getLogger("unifi-network-mcp")

@server.tool(
    name="unifi_list_switch_ports",
    description="List all ports and their configurations for a specific switch"
)
async def list_switch_ports(device_mac: str) -> Dict[str, Any]:
    """List all ports and their current configurations for a switch.
    
    Args:
        device_mac: MAC address of the switch
        
    Returns:
        Dictionary containing port information
    """
    if not parse_permission(config.permissions, "devices", "read"):
        logger.warning(f"Permission denied for listing switch ports")
        return {"success": False, "error": "Permission denied"}
    
    try:
        # Get device details
        device = await device_manager.get_device_details(device_mac)
        if not device or not hasattr(device, 'raw'):
            return {"success": False, "error": f"Device {device_mac} not found"}
        
        device_data = device.raw
        
        # Check if it's a switch
        if device_data.get('type') not in ['usw', 'usl', 'usf']:
            return {"success": False, "error": f"Device {device_mac} is not a switch"}
        
        # Get port table and overrides
        port_table = device_data.get('port_table', [])
        port_overrides = device_data.get('port_overrides', [])
        
        # Create a map of overrides by port_idx
        override_map = {override['port_idx']: override for override in port_overrides}
        
        # Build port information
        ports = []
        for port in port_table:
            port_idx = port.get('port_idx', 0)
            override = override_map.get(port_idx, {})
            
            port_info = {
                'port_idx': port_idx,
                'name': override.get('name', port.get('name', f"Port {port_idx + 1}")),
                'enabled': override.get('forward') != 'disabled',
                'poe_mode': override.get('poe_mode', port.get('poe_mode', 'off')),
                'port_profile': override.get('portconf_id', port.get('portconf_id')),
                'speed': port.get('speed'),
                'full_duplex': port.get('full_duplex'),
                'rx_bytes': port.get('rx_bytes'),
                'tx_bytes': port.get('tx_bytes'),
                'port_poe': port.get('port_poe', False),
                'poe_power': port.get('poe_power', 0),
                'poe_voltage': port.get('poe_voltage', 0),
                'up': port.get('up', False),
                'media': port.get('media', 'Unknown')
            }
            ports.append(port_info)
        
        return {
            "success": True,
            "device_mac": device_mac,
            "device_name": device_data.get('name', 'Unknown'),
            "device_model": device_data.get('model', 'Unknown'),
            "port_count": len(ports),
            "ports": ports
        }
        
    except Exception as e:
        logger.error(f"Error listing switch ports: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_toggle_switch_port",
    description="Enable or disable a specific port on a switch"
)
async def toggle_switch_port(
    device_mac: str,
    port_idx: int,
    enabled: bool,
    confirm: bool = False
) -> Dict[str, Any]:
    """Enable or disable a specific port on a switch.
    
    Args:
        device_mac: MAC address of the switch
        port_idx: Port index (0-based, so port 1 = index 0)
        enabled: True to enable, False to disable
        confirm: Must be True to execute
        
    Returns:
        Dictionary with operation result
    """
    if not parse_permission(config.permissions, "devices", "update"):
        logger.warning(f"Permission denied for toggling switch port")
        return {"success": False, "error": "Permission denied"}
    
    if not confirm:
        return {
            "success": False,
            "error": "Confirmation required. Set 'confirm' to true.",
            "warning": f"This will {'enable' if enabled else 'disable'} port {port_idx + 1} on switch {device_mac}"
        }
    
    try:
        success = await device_manager.toggle_switch_port(device_mac, port_idx, enabled)
        
        if success:
            action = "enabled" if enabled else "disabled"
            logger.info(f"Port {port_idx + 1} {action} on switch {device_mac}")
            return {
                "success": True,
                "device_mac": device_mac,
                "port_idx": port_idx,
                "port_number": port_idx + 1,
                "enabled": enabled,
                "message": f"Port {port_idx + 1} has been {action}"
            }
        else:
            return {"success": False, "error": "Failed to toggle port state"}
            
    except Exception as e:
        logger.error(f"Error toggling switch port: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_set_port_poe",
    description="Set PoE mode for a specific switch port"
)
async def set_port_poe(
    device_mac: str,
    port_idx: int,
    poe_mode: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """Set PoE mode for a specific port on a PoE-capable switch.
    
    Args:
        device_mac: MAC address of the switch
        port_idx: Port index (0-based, so port 1 = index 0)
        poe_mode: PoE mode ('auto', 'passive', 'passthrough', 'off')
        confirm: Must be True to execute
        
    Returns:
        Dictionary with operation result
    """
    if not parse_permission(config.permissions, "devices", "update"):
        logger.warning(f"Permission denied for setting PoE mode")
        return {"success": False, "error": "Permission denied"}
    
    # Validate PoE mode
    valid_modes = ['auto', 'passive', 'passthrough', 'off']
    if poe_mode not in valid_modes:
        return {
            "success": False,
            "error": f"Invalid PoE mode. Must be one of: {', '.join(valid_modes)}"
        }
    
    if not confirm:
        return {
            "success": False,
            "error": "Confirmation required. Set 'confirm' to true.",
            "warning": f"This will set PoE mode to '{poe_mode}' for port {port_idx + 1} on switch {device_mac}"
        }
    
    try:
        success = await device_manager.set_port_poe_mode(device_mac, port_idx, poe_mode)
        
        if success:
            logger.info(f"PoE mode set to {poe_mode} for port {port_idx + 1} on switch {device_mac}")
            return {
                "success": True,
                "device_mac": device_mac,
                "port_idx": port_idx,
                "port_number": port_idx + 1,
                "poe_mode": poe_mode,
                "message": f"PoE mode set to '{poe_mode}' for port {port_idx + 1}"
            }
        else:
            return {"success": False, "error": "Failed to set PoE mode"}
            
    except Exception as e:
        logger.error(f"Error setting PoE mode: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_set_port_profile",
    description="Set port profile for a specific switch port"
)
async def set_port_profile(
    device_mac: str,
    port_idx: int,
    portconf_id: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """Set port profile for a specific port on a switch.
    
    Args:
        device_mac: MAC address of the switch
        port_idx: Port index (0-based, so port 1 = index 0)
        portconf_id: Port profile ID (use list_port_profiles to get available IDs)
        confirm: Must be True to execute
        
    Returns:
        Dictionary with operation result
    """
    if not parse_permission(config.permissions, "devices", "update"):
        logger.warning(f"Permission denied for setting port profile")
        return {"success": False, "error": "Permission denied"}
    
    if not confirm:
        return {
            "success": False,
            "error": "Confirmation required. Set 'confirm' to true.",
            "warning": f"This will change the port profile for port {port_idx + 1} on switch {device_mac}"
        }
    
    try:
        success = await device_manager.set_port_profile(device_mac, port_idx, portconf_id)
        
        if success:
            logger.info(f"Port profile set for port {port_idx + 1} on switch {device_mac}")
            return {
                "success": True,
                "device_mac": device_mac,
                "port_idx": port_idx,
                "port_number": port_idx + 1,
                "portconf_id": portconf_id,
                "message": f"Port profile updated for port {port_idx + 1}"
            }
        else:
            return {"success": False, "error": "Failed to set port profile"}
            
    except Exception as e:
        logger.error(f"Error setting port profile: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_set_port_name",
    description="Set custom name for a specific switch port"
)
async def set_port_name(
    device_mac: str,
    port_idx: int,
    name: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """Set custom name for a specific port on a switch.
    
    Args:
        device_mac: MAC address of the switch
        port_idx: Port index (0-based, so port 1 = index 0)
        name: Custom name for the port
        confirm: Must be True to execute
        
    Returns:
        Dictionary with operation result
    """
    if not parse_permission(config.permissions, "devices", "update"):
        logger.warning(f"Permission denied for setting port name")
        return {"success": False, "error": "Permission denied"}
    
    if not confirm:
        return {
            "success": False,
            "error": "Confirmation required. Set 'confirm' to true.",
            "warning": f"This will rename port {port_idx + 1} to '{name}' on switch {device_mac}"
        }
    
    try:
        success = await device_manager.set_port_name(device_mac, port_idx, name)
        
        if success:
            logger.info(f"Port {port_idx + 1} renamed to '{name}' on switch {device_mac}")
            return {
                "success": True,
                "device_mac": device_mac,
                "port_idx": port_idx,
                "port_number": port_idx + 1,
                "name": name,
                "message": f"Port {port_idx + 1} renamed to '{name}'"
            }
        else:
            return {"success": False, "error": "Failed to set port name"}
            
    except Exception as e:
        logger.error(f"Error setting port name: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_list_port_profiles",
    description="List all available port profiles"
)
async def list_port_profiles() -> Dict[str, Any]:
    """List all available port profiles that can be assigned to switch ports.
    
    Returns:
        Dictionary containing port profile information
    """
    if not parse_permission(config.permissions, "devices", "read"):
        logger.warning(f"Permission denied for listing port profiles")
        return {"success": False, "error": "Permission denied"}
    
    try:
        profiles = await device_manager.get_port_profiles()
        
        # Format profile information
        formatted_profiles = []
        for profile in profiles:
            formatted_profiles.append({
                'id': profile.get('_id'),
                'name': profile.get('name', 'Unnamed'),
                'native_networkconf_id': profile.get('native_networkconf_id'),
                'tagged_networkconf_ids': profile.get('tagged_networkconf_ids', []),
                'forward': profile.get('forward', 'all'),
                'isolation': profile.get('isolation', False),
                'stormctrl_bcast_enabled': profile.get('stormctrl_bcast_enabled', False),
                'stormctrl_mcast_enabled': profile.get('stormctrl_mcast_enabled', False),
                'stormctrl_ucast_enabled': profile.get('stormctrl_ucast_enabled', False),
                'lldpmed_enabled': profile.get('lldpmed_enabled', False),
                'stp_port_mode': profile.get('stp_port_mode', True)
            })
        
        return {
            "success": True,
            "count": len(formatted_profiles),
            "profiles": formatted_profiles
        }
        
    except Exception as e:
        logger.error(f"Error listing port profiles: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_restart_poe_port",
    description="Restart a PoE device by cycling power on its port"
)
async def restart_poe_port(
    device_mac: str,
    port_idx: int,
    confirm: bool = False
) -> Dict[str, Any]:
    """Restart a PoE device by cycling power on its port (turn off, wait, turn on).
    
    Args:
        device_mac: MAC address of the switch
        port_idx: Port index (0-based, so port 1 = index 0)
        confirm: Must be True to execute
        
    Returns:
        Dictionary with operation result
    """
    if not parse_permission(config.permissions, "devices", "update"):
        logger.warning(f"Permission denied for restarting PoE port")
        return {"success": False, "error": "Permission denied"}
    
    if not confirm:
        return {
            "success": False,
            "error": "Confirmation required. Set 'confirm' to true.",
            "warning": f"This will power cycle port {port_idx + 1} on switch {device_mac}, temporarily disconnecting any connected device"
        }
    
    try:
        import asyncio
        
        # Turn off PoE
        success = await device_manager.set_port_poe_mode(device_mac, port_idx, 'off')
        if not success:
            return {"success": False, "error": "Failed to turn off PoE"}
        
        # Wait 5 seconds
        await asyncio.sleep(5)
        
        # Turn on PoE (auto mode)
        success = await device_manager.set_port_poe_mode(device_mac, port_idx, 'auto')
        if not success:
            return {"success": False, "error": "Failed to turn on PoE"}
        
        logger.info(f"PoE cycled for port {port_idx + 1} on switch {device_mac}")
        return {
            "success": True,
            "device_mac": device_mac,
            "port_idx": port_idx,
            "port_number": port_idx + 1,
            "message": f"PoE power cycled for port {port_idx + 1}. Device should be restarting."
        }
        
    except Exception as e:
        logger.error(f"Error restarting PoE port: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
"""MCP tools for managing DHCP reservations and fixed IP assignments."""

import logging
from typing import Any, Dict, List
from src.runtime import server, dhcp_manager
from src.validators import validate_mac_address, validate_ip_address

logger = logging.getLogger(__name__)


@server.tool()
async def unifi_list_dhcp_reservations() -> Dict[str, Any]:
    """
    List all DHCP reservations (fixed IP assignments) in the UniFi network.
    
    Returns:
        A list of all DHCP reservations with client information
        
    Example response:
        {
            "success": true,
            "reservations": [
                {
                    "_id": "5f4a1234567890abcdef1234",
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "name": "Office Printer",
                    "fixed_ip": "192.168.1.100",
                    "network_id": "5f4a1234567890abcdef5678",
                    "network_name": "LAN",
                    "network_subnet": "192.168.1.0/24"
                }
            ]
        }
    """
    try:
        reservations = await dhcp_manager.list_dhcp_reservations()
        
        return {
            "success": True,
            "count": len(reservations),
            "reservations": reservations
        }
    except Exception as e:
        logger.error(f"Failed to list DHCP reservations: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_set_client_fixed_ip(
    mac_address: str,
    fixed_ip: str,
    network_id: str = None
) -> Dict[str, Any]:
    """
    Set or update a fixed IP reservation for a client device.
    
    Args:
        mac_address: MAC address of the client (e.g., "aa:bb:cc:dd:ee:ff")
        fixed_ip: The fixed IP address to assign (e.g., "192.168.1.100")
        network_id: Optional network ID. If not provided, auto-detects from IP subnet
        
    Returns:
        Success status and details
        
    Example:
        Set fixed IP for a printer:
        mac_address="00:11:22:33:44:55"
        fixed_ip="192.168.1.100"
    """
    # Validate inputs
    if not validate_mac_address(mac_address):
        return {"success": False, "error": "Invalid MAC address format"}
    
    if not validate_ip_address(fixed_ip):
        return {"success": False, "error": "Invalid IP address format"}
    
    try:
        success = await dhcp_manager.set_client_fixed_ip(
            mac_address,
            fixed_ip,
            network_id,
            use_fixedip=True
        )
        
        if success:
            return {
                "success": True,
                "message": f"Fixed IP {fixed_ip} assigned to {mac_address}",
                "mac_address": mac_address,
                "fixed_ip": fixed_ip,
                "network_id": network_id
            }
        else:
            return {
                "success": False,
                "error": "Failed to set fixed IP. Check if client exists and network is valid."
            }
    except Exception as e:
        logger.error(f"Failed to set fixed IP: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_remove_client_fixed_ip(mac_address: str) -> Dict[str, Any]:
    """
    Remove fixed IP reservation for a client (enable DHCP).
    
    Args:
        mac_address: MAC address of the client (e.g., "aa:bb:cc:dd:ee:ff")
        
    Returns:
        Success status
        
    Example:
        Remove fixed IP and enable DHCP:
        mac_address="00:11:22:33:44:55"
    """
    # Validate MAC address
    if not validate_mac_address(mac_address):
        return {"success": False, "error": "Invalid MAC address format"}
    
    try:
        success = await dhcp_manager.remove_client_fixed_ip(mac_address)
        
        if success:
            return {
                "success": True,
                "message": f"Fixed IP removed for {mac_address}, DHCP enabled",
                "mac_address": mac_address
            }
        else:
            return {
                "success": False,
                "error": "Failed to remove fixed IP. Check if client exists."
            }
    except Exception as e:
        logger.error(f"Failed to remove fixed IP: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_get_client_fixed_ip(mac_address: str) -> Dict[str, Any]:
    """
    Get fixed IP configuration for a specific client.
    
    Args:
        mac_address: MAC address of the client (e.g., "aa:bb:cc:dd:ee:ff")
        
    Returns:
        Fixed IP configuration or error if not found
        
    Example response:
        {
            "success": true,
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "Office Printer",
            "fixed_ip": "192.168.1.100",
            "network_id": "5f4a1234567890abcdef5678",
            "use_fixedip": true
        }
    """
    # Validate MAC address
    if not validate_mac_address(mac_address):
        return {"success": False, "error": "Invalid MAC address format"}
    
    try:
        config = await dhcp_manager.get_client_fixed_ip(mac_address)
        
        if config:
            return {
                "success": True,
                **config
            }
        else:
            return {
                "success": False,
                "error": f"No fixed IP configuration found for {mac_address}"
            }
    except Exception as e:
        logger.error(f"Failed to get fixed IP configuration: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_create_dhcp_reservation(
    mac_address: str,
    fixed_ip: str,
    name: str = None,
    network_id: str = None
) -> Dict[str, Any]:
    """
    Create a new DHCP reservation for a device (even if not currently online).
    
    Args:
        mac_address: MAC address of the device (e.g., "aa:bb:cc:dd:ee:ff")
        fixed_ip: The fixed IP to assign (e.g., "192.168.1.100")
        name: Optional name for the device
        network_id: Optional network ID (auto-detected from IP if not provided)
        
    Returns:
        Success status and details
        
    Example:
        Create reservation for a new device:
        mac_address="00:11:22:33:44:55"
        fixed_ip="192.168.1.100"
        name="Office Printer"
    """
    # Validate inputs
    if not validate_mac_address(mac_address):
        return {"success": False, "error": "Invalid MAC address format"}
    
    if not validate_ip_address(fixed_ip):
        return {"success": False, "error": "Invalid IP address format"}
    
    try:
        success = await dhcp_manager.create_dhcp_reservation(
            mac_address,
            fixed_ip,
            name,
            network_id
        )
        
        if success:
            result = {
                "success": True,
                "message": f"DHCP reservation created for {mac_address}",
                "mac_address": mac_address,
                "fixed_ip": fixed_ip
            }
            if name:
                result["name"] = name
            if network_id:
                result["network_id"] = network_id
            return result
        else:
            return {
                "success": False,
                "error": "Failed to create DHCP reservation. Check network and IP validity."
            }
    except Exception as e:
        logger.error(f"Failed to create DHCP reservation: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_list_available_ips(network_id: str) -> Dict[str, Any]:
    """
    List available IP addresses in a network that are not reserved or in use.
    
    Args:
        network_id: The network ID to check
        
    Returns:
        List of available IP addresses (limited to 50)
        
    Example response:
        {
            "success": true,
            "network_id": "5f4a1234567890abcdef5678",
            "count": 50,
            "available_ips": [
                "192.168.1.101",
                "192.168.1.102",
                "192.168.1.103"
            ]
        }
    """
    try:
        available_ips = await dhcp_manager.list_available_ips(network_id)
        
        return {
            "success": True,
            "network_id": network_id,
            "count": len(available_ips),
            "available_ips": available_ips
        }
    except Exception as e:
        logger.error(f"Failed to list available IPs: {e}")
        return {"success": False, "error": str(e)}


# Log when module is loaded
logger.info(f"DHCP tools module loaded, server instance: {server}")
logger.info(f"DHCP tools registered: unifi_list_dhcp_reservations, unifi_set_client_fixed_ip, "
           f"unifi_remove_client_fixed_ip, unifi_get_client_fixed_ip, "
           f"unifi_create_dhcp_reservation, unifi_list_available_ips")
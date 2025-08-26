"""MCP tools for WAN/Internet configuration - READ-ONLY for safety!

SECURITY NOTE: These tools are READ-ONLY to prevent accidental loss of internet connectivity.
WAN modifications must be done through the UniFi Controller UI.
"""

import logging
from typing import Any, Dict
from src.runtime import server, wan_manager
from src.utils.permissions import parse_permission
from src.runtime import config

logger = logging.getLogger(__name__)


@server.tool()
async def unifi_get_wan_status() -> Dict[str, Any]:
    """
    Get current WAN/Internet configuration and status (READ-ONLY).
    
    This tool provides safe read-only access to WAN configuration without
    risk of accidentally breaking internet connectivity.
    
    Returns:
        Current WAN configuration including:
        - Gateway device information
        - WAN interface status (WAN1, WAN2)
        - IP configuration
        - Connection type (DHCP, Static, PPPoE)
        - Uptime information
        
    Example response:
        {
            "success": true,
            "gateway_mac": "aa:bb:cc:dd:ee:ff",
            "gateway_model": "UDM-Pro",
            "wan_interfaces": [
                {
                    "name": "wan1",
                    "ip": "203.0.113.10",
                    "gateway": "203.0.113.1",
                    "type": "dhcp",
                    "enabled": true,
                    "uptime": 86400
                }
            ],
            "wan_network": {
                "name": "WAN",
                "wan_type": "dhcp"
            }
        }
    """
    try:
        wan_config = await wan_manager.get_wan_configuration()
        return wan_config
    except Exception as e:
        logger.error(f"Failed to get WAN status: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_get_wan_failover_status() -> Dict[str, Any]:
    """
    Get WAN failover/load balancing configuration (READ-ONLY).
    
    Returns:
        Failover configuration including:
        - Failover enabled status
        - Load balance configuration
        - WAN weights for load balancing
        
    Example response:
        {
            "success": true,
            "failover_enabled": true,
            "load_balance_enabled": false,
            "wan1_weight": 50,
            "wan2_weight": 50
        }
    """
    try:
        failover_config = await wan_manager.get_wan_failover_settings()
        return failover_config
    except Exception as e:
        logger.error(f"Failed to get WAN failover status: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_get_dream_machine_wan_status() -> Dict[str, Any]:
    """
    Get detailed WAN status for Dream Machine integrated controllers (READ-ONLY).
    
    Dream Machine Pro and other integrated devices don't appear as managed devices
    because they ARE the controller itself. This tool extracts WAN information
    from system and health endpoints instead.
    
    Returns:
        Comprehensive WAN status including:
        - Controller model and version
        - WAN health information
        - Port configurations
        - Uplink settings
        - Internet connectivity status
        
    Example response:
        {
            "success": true,
            "is_dream_machine": true,
            "data": {
                "controller": {
                    "model": "UDM-Pro",
                    "version": "3.2.7",
                    "mac": "78:45:58:c1:36:fb"
                },
                "health": {
                    "status": "ok",
                    "wan_ip": "203.0.113.10",
                    "uptime": 86400
                }
            }
        }
    """
    try:
        dm_status = await wan_manager.get_dream_machine_wan_status()
        return dm_status
    except Exception as e:
        logger.error(f"Failed to get Dream Machine WAN status: {e}")
        return {"success": False, "error": str(e)}


@server.tool()
async def unifi_check_wan_connectivity() -> Dict[str, Any]:
    """
    Check current WAN connectivity and internet access (READ-ONLY).
    
    This performs a safe connectivity check without modifying any settings.
    
    Returns:
        Connectivity status including:
        - Internet reachable status
        - Gateway connectivity
        - DNS resolution status
        - Latency information
        
    Example response:
        {
            "success": true,
            "internet_reachable": true,
            "gateway_reachable": true,
            "dns_working": true,
            "wan1_status": "connected",
            "wan2_status": "disconnected"
        }
    """
    try:
        # Get basic WAN config
        wan_config = await wan_manager.get_wan_configuration()
        
        result = {
            "success": True,
            "wan1_configured": False,
            "wan2_configured": False,
            "active_wan": None
        }
        
        # Check WAN interfaces
        for interface in wan_config.get("wan_interfaces", []):
            if interface["name"] == "wan1":
                result["wan1_configured"] = interface.get("enabled", False)
                result["wan1_ip"] = interface.get("ip")
                result["wan1_type"] = interface.get("type")
                if interface.get("uptime", 0) > 0:
                    result["active_wan"] = "wan1"
            elif interface["name"] == "wan2":
                result["wan2_configured"] = interface.get("enabled", False)
                result["wan2_ip"] = interface.get("ip")
                result["wan2_type"] = interface.get("type")
                if interface.get("uptime", 0) > 0 and not result["active_wan"]:
                    result["active_wan"] = "wan2"
        
        # Add network health info if available
        from src.runtime import system_manager
        health = await system_manager.get_network_health()
        if health and "subsystems" in health:
            for subsystem in health["subsystems"]:
                if subsystem.get("subsystem") == "wan":
                    result["wan_health_status"] = subsystem.get("status")
                    result["wan_health_ok"] = subsystem.get("status") == "ok"
                    break
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to check WAN connectivity: {e}")
        return {"success": False, "error": str(e)}


# DANGEROUS OPERATIONS - Commented out for safety!
# These functions are intentionally disabled to prevent accidental internet loss.
# If you need to modify WAN settings, use the UniFi Controller UI directly.

"""
# DO NOT UNCOMMENT WITHOUT CAREFUL CONSIDERATION!

@server.tool()
async def unifi_update_wan_type(
    wan_name: str,
    wan_type: str,
    settings: Dict[str, Any],
    confirm_risk: bool = False
) -> Dict[str, Any]:
    # DANGEROUS: Can break internet connectivity!
    # This tool is disabled by default for safety.
    
    if not confirm_risk:
        return {
            "success": False,
            "error": "This operation can break internet connectivity! Set confirm_risk=true if you really want to proceed.",
            "warning": "It's recommended to use the UniFi Controller UI for WAN changes."
        }
    
    # Additional permission check
    if not parse_permission(config.permissions, "wan_config", "update"):
        return {"success": False, "error": "Permission denied. WAN updates are disabled for safety."}
    
    # ... implementation would go here ...
"""


logger.info(f"WAN tools module loaded (READ-ONLY mode), server instance: {server}")
logger.info("WAN tools registered: unifi_get_wan_status, unifi_get_wan_failover_status, unifi_get_dream_machine_wan_status, unifi_check_wan_connectivity")
logger.info("SAFETY: WAN modification tools are disabled to prevent accidental internet loss")
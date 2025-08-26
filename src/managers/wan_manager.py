"""WAN Manager for handling WAN port configuration and uplink management."""

import logging
from typing import Dict, List, Any, Optional
from aiounifi.models.api import ApiRequest, ApiRequestV2

logger = logging.getLogger(__name__)


class WANManager:
    """Manager for WAN/Internet configuration and uplink management."""
    
    def __init__(self, connection):
        """Initialize WAN manager with connection."""
        self.connection = connection
        
    async def get_wan_configuration(self) -> Dict[str, Any]:
        """
        Get current WAN configuration including all uplinks.
        
        Returns:
            Dictionary with WAN configuration details
        """
        await self.connection.ensure_connected()
        
        try:
            # Get gateway device info for WAN status
            devices = self.connection.controller.devices.values()
            gateway_device = None
            
            for device in devices:
                if device.type in ['ugw', 'udm', 'uxg', 'udmp']:
                    gateway_device = device
                    break
            
            if not gateway_device:
                return {
                    "success": False,
                    "error": "No gateway device found"
                }
            
            wan_config = {
                "success": True,
                "gateway_mac": gateway_device.mac,
                "gateway_model": gateway_device.model,
                "wan_interfaces": []
            }
            
            # Extract WAN interface information
            if hasattr(gateway_device, 'wan1'):
                wan1 = gateway_device.wan1
                wan_config["wan_interfaces"].append({
                    "name": "wan1",
                    "ip": wan1.get('ip'),
                    "netmask": wan1.get('netmask'),
                    "gateway": wan1.get('gateway'),
                    "dns": wan1.get('dns'),
                    "type": wan1.get('type', 'dhcp'),
                    "enabled": wan1.get('enable', True),
                    "uptime": wan1.get('uptime')
                })
            
            if hasattr(gateway_device, 'wan2'):
                wan2 = gateway_device.wan2
                wan_config["wan_interfaces"].append({
                    "name": "wan2",
                    "ip": wan2.get('ip'),
                    "netmask": wan2.get('netmask'),
                    "gateway": wan2.get('gateway'),
                    "dns": wan2.get('dns'),
                    "type": wan2.get('type', 'disabled'),
                    "enabled": wan2.get('enable', False),
                    "uptime": wan2.get('uptime')
                })
            
            # Get WAN network configuration
            api_request = ApiRequest(
                method="get",
                path="/rest/networkconf"
            )
            networks = await self.connection.request(api_request)
            
            for network in networks:
                if network.get('purpose') == 'wan':
                    wan_config['wan_network'] = {
                        '_id': network.get('_id'),
                        'name': network.get('name'),
                        'wan_type': network.get('wan_type', 'dhcp'),
                        'wan_ip': network.get('wan_ip'),
                        'wan_netmask': network.get('wan_netmask'),
                        'wan_gateway': network.get('wan_gateway'),
                        'wan_dns1': network.get('wan_dns1'),
                        'wan_dns2': network.get('wan_dns2'),
                        'wan_dhcp_options': network.get('wan_dhcp_options', [])
                    }
                    break
            
            return wan_config
            
        except Exception as e:
            logger.error(f"Failed to get WAN configuration: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_wan_type(self, wan_name: str, wan_type: str, settings: Dict[str, Any]) -> bool:
        """
        Update WAN connection type (DHCP, Static, PPPoE).
        WARNING: This can disrupt internet connectivity!
        
        Args:
            wan_name: Interface name ('wan1' or 'wan2')
            wan_type: Connection type ('dhcp', 'static', 'pppoe')
            settings: Type-specific settings (IP, gateway, DNS for static; username/password for PPPoE)
            
        Returns:
            True if successful, False otherwise
        """
        await self.connection.ensure_connected()
        
        if wan_name not in ['wan1', 'wan2']:
            logger.error(f"Invalid WAN interface: {wan_name}")
            return False
        
        if wan_type not in ['dhcp', 'static', 'pppoe']:
            logger.error(f"Invalid WAN type: {wan_type}")
            return False
        
        try:
            # Get current WAN network configuration
            api_request = ApiRequest(
                method="get",
                path="/rest/networkconf"
            )
            networks = await self.connection.request(api_request)
            
            wan_network = None
            for network in networks:
                if network.get('purpose') == 'wan':
                    wan_network = network
                    break
            
            if not wan_network:
                logger.error("WAN network configuration not found")
                return False
            
            # Prepare update data
            update_data = {
                '_id': wan_network['_id'],
                'wan_type': wan_type
            }
            
            # Add type-specific settings
            if wan_type == 'static':
                required = ['wan_ip', 'wan_netmask', 'wan_gateway']
                for field in required:
                    if field not in settings:
                        logger.error(f"Missing required field for static WAN: {field}")
                        return False
                    update_data[field] = settings[field]
                
                # Optional DNS settings
                if 'wan_dns1' in settings:
                    update_data['wan_dns1'] = settings['wan_dns1']
                if 'wan_dns2' in settings:
                    update_data['wan_dns2'] = settings['wan_dns2']
            
            elif wan_type == 'pppoe':
                required = ['wan_username', 'wan_password']
                for field in required:
                    if field not in settings:
                        logger.error(f"Missing required field for PPPoE: {field}")
                        return False
                    update_data[field] = settings[field]
            
            # Update the network configuration
            api_request = ApiRequest(
                method="put",
                path=f"/rest/networkconf/{wan_network['_id']}",
                data=update_data
            )
            
            await self.connection.request(api_request)
            
            logger.warning(f"WAN configuration updated for {wan_name} to {wan_type}. Internet connectivity may be affected!")
            self.connection._invalidate_cache()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update WAN type: {e}")
            return False
    
    async def get_wan_failover_settings(self) -> Dict[str, Any]:
        """
        Get WAN failover/load balancing settings.
        
        Returns:
            Failover configuration
        """
        await self.connection.ensure_connected()
        
        try:
            # This would typically be in site settings
            api_request = ApiRequest(
                method="get",
                path="/get/setting/connectivity"
            )
            settings = await self.connection.request(api_request)
            
            if settings and isinstance(settings, list) and len(settings) > 0:
                connectivity = settings[0]
                return {
                    "success": True,
                    "failover_enabled": connectivity.get('uplink_type', 'failover') == 'failover',
                    "load_balance_enabled": connectivity.get('uplink_type') == 'weighted',
                    "wan1_weight": connectivity.get('wan1_weight', 50),
                    "wan2_weight": connectivity.get('wan2_weight', 50)
                }
            
            return {
                "success": False,
                "error": "No connectivity settings found"
            }
            
        except Exception as e:
            logger.error(f"Failed to get WAN failover settings: {e}")
            return {"success": False, "error": str(e)}
    
    async def set_wan_failover(self, mode: str, wan1_weight: int = 50, wan2_weight: int = 50) -> bool:
        """
        Configure WAN failover or load balancing.
        
        Args:
            mode: 'failover' or 'weighted' (load balance)
            wan1_weight: Weight for WAN1 in load balance mode (1-100)
            wan2_weight: Weight for WAN2 in load balance mode (1-100)
            
        Returns:
            True if successful
        """
        await self.connection.ensure_connected()
        
        if mode not in ['failover', 'weighted']:
            logger.error(f"Invalid failover mode: {mode}")
            return False
        
        try:
            # Get current settings
            api_request = ApiRequest(
                method="get",
                path="/get/setting/connectivity"
            )
            settings = await self.connection.request(api_request)
            
            if not settings or not isinstance(settings, list):
                logger.error("Could not retrieve current connectivity settings")
                return False
            
            current = settings[0] if settings else {}
            
            # Update settings
            update_data = {
                '_id': current.get('_id'),
                'key': 'connectivity',
                'uplink_type': mode
            }
            
            if mode == 'weighted':
                update_data['wan1_weight'] = max(1, min(100, wan1_weight))
                update_data['wan2_weight'] = max(1, min(100, wan2_weight))
            
            api_request = ApiRequest(
                method="put",
                path="/set/setting/connectivity",
                data=update_data
            )
            
            await self.connection.request(api_request)
            
            logger.info(f"WAN failover mode set to {mode}")
            self.connection._invalidate_cache()
            return True
            
        except Exception as e:
            logger.error(f"Failed to set WAN failover: {e}")
            return False
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
        For Dream Machine Pro and other integrated controllers, this extracts
        WAN info from system/health endpoints since they don't appear as managed devices.
        
        Returns:
            Dictionary with WAN configuration details
        """
        await self.connection.ensure_connected()
        
        try:
            wan_config = {
                "success": True,
                "wan_interfaces": []
            }
            
            # First try to get WAN info from devices (for separate gateways)
            devices = self.connection.controller.devices.values()
            gateway_device = None
            
            for device in devices:
                if hasattr(device, 'type') and device.type in ['ugw', 'udm', 'uxg', 'udmp']:
                    gateway_device = device
                    break
            
            if gateway_device:
                # Found a managed gateway device
                wan_config["gateway_mac"] = gateway_device.mac
                wan_config["gateway_model"] = gateway_device.model
                wan_config["source"] = "device"
                
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
            else:
                # No managed gateway - try system info (for Dream Machine Pro etc.)
                logger.info("No managed gateway device found, checking system info for integrated controller/gateway")
                
                # Get system info to identify controller type
                api_request = ApiRequest(
                    method="get",
                    path="/stat/sysinfo"
                )
                sysinfo = await self.connection.request(api_request)
                
                if sysinfo and isinstance(sysinfo, dict):
                    wan_config["gateway_model"] = sysinfo.get('model', 'Unknown')
                    wan_config["gateway_version"] = sysinfo.get('version', 'Unknown')
                    wan_config["source"] = "sysinfo"
                    
                    # For Dream Machines, check health status for WAN info
                    if 'dream' in str(sysinfo.get('model', '')).lower() or 'udm' in str(sysinfo.get('model', '')).lower():
                        # Get health status which contains WAN info for integrated gateways
                        health_request = ApiRequest(
                            method="get",
                            path="/stat/health"
                        )
                        health_data = await self.connection.request(health_request)
                        
                        if health_data and isinstance(health_data, list):
                            for subsystem in health_data:
                                if subsystem.get('subsystem') == 'wan':
                                    wan_config["wan_health"] = {
                                        "status": subsystem.get('status'),
                                        "num_adopted": subsystem.get('num_adopted', 0),
                                        "num_disconnected": subsystem.get('num_disconnected', 0),
                                        "num_pending": subsystem.get('num_pending', 0),
                                        "wan_ip": subsystem.get('wan_ip'),
                                        "gw_name": subsystem.get('gw_name'),
                                        "gw_mac": subsystem.get('gw_mac'),
                                        "gw_version": subsystem.get('gw_version'),
                                        "uptime": subsystem.get('uptime'),
                                        "latency": subsystem.get('latency'),
                                        "xput_up": subsystem.get('xput_up'),
                                        "xput_down": subsystem.get('xput_down'),
                                        "speedtest_status": subsystem.get('speedtest_status'),
                                        "speedtest_lastrun": subsystem.get('speedtest_lastrun'),
                                        "speedtest_ping": subsystem.get('speedtest_ping')
                                    }
                                    
                                    # If we found a gateway MAC in health, record it
                                    if subsystem.get('gw_mac'):
                                        wan_config["gateway_mac"] = subsystem.get('gw_mac')
                                    break
                        
                        # Try to get more detailed WAN info from site stats
                        site_request = ApiRequest(
                            method="get",
                            path="/stat/sites"
                        )
                        site_data = await self.connection.request(site_request)
                        
                        if site_data and isinstance(site_data, list) and len(site_data) > 0:
                            site = site_data[0]
                            if 'wan_ip' in site:
                                wan_config["wan_interfaces"].append({
                                    "name": "wan",
                                    "ip": site.get('wan_ip'),
                                    "type": "detected",
                                    "enabled": True
                                })
            
            # Get WAN network configuration (works for all setups)
            api_request = ApiRequest(
                method="get",
                path="/rest/networkconf"
            )
            networks = await self.connection.request(api_request)
            
            if networks and isinstance(networks, list):
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
    
    async def get_dream_machine_wan_status(self) -> Dict[str, Any]:
        """
        Get detailed WAN status specifically for Dream Machine integrated controllers.
        This method uses multiple endpoints to gather comprehensive WAN information
        when the gateway is the controller itself (not a separate managed device).
        
        Returns:
            Detailed WAN status including IP, uptime, speed test results, and more
        """
        await self.connection.ensure_connected()
        
        try:
            wan_status = {
                "success": True,
                "is_dream_machine": False,
                "data": {}
            }
            
            # Step 1: Confirm this is a Dream Machine
            api_request = ApiRequest(
                method="get",
                path="/stat/sysinfo"
            )
            sysinfo = await self.connection.request(api_request)
            
            if not sysinfo or not isinstance(sysinfo, dict):
                return {"success": False, "error": "Could not get system info"}
            
            model = str(sysinfo.get('model', '')).lower()
            if not ('dream' in model or 'udm' in model or 'uxg' in model):
                return {
                    "success": False,
                    "error": f"Not a Dream Machine (model: {sysinfo.get('model')})"
                }
            
            wan_status["is_dream_machine"] = True
            wan_status["data"]["controller"] = {
                "model": sysinfo.get('model'),
                "version": sysinfo.get('version'),
                "hostname": sysinfo.get('hostname'),
                "mac": sysinfo.get('mac')
            }
            
            # Step 2: Get WAN health status
            health_request = ApiRequest(
                method="get",
                path="/stat/health"
            )
            health_data = await self.connection.request(health_request)
            
            if health_data and isinstance(health_data, list):
                for subsystem in health_data:
                    if subsystem.get('subsystem') == 'wan':
                        wan_status["data"]["health"] = subsystem
                        break
            
            # Step 3: Get detailed device stats (even if not in device list)
            # Try to get the Dream Machine's own stats
            if sysinfo.get('mac'):
                try:
                    device_stat_request = ApiRequest(
                        method="get",
                        path=f"/stat/device/{sysinfo['mac']}"
                    )
                    device_stats = await self.connection.request(device_stat_request)
                    if device_stats:
                        wan_status["data"]["device_stats"] = device_stats
                except Exception as e:
                    logger.debug(f"Could not get device stats for controller: {e}")
            
            # Step 4: Get port information (WAN is typically port 9)
            try:
                port_request = ApiRequest(
                    method="get",
                    path="/rest/portconf"
                )
                port_configs = await self.connection.request(port_request)
                if port_configs and isinstance(port_configs, list):
                    wan_status["data"]["port_configs"] = port_configs
            except Exception as e:
                logger.debug(f"Could not get port configs: {e}")
            
            # Step 5: Get uplink information
            try:
                uplink_request = ApiRequest(
                    method="get",
                    path="/rest/setting/connectivity"
                )
                uplink_settings = await self.connection.request(uplink_request)
                if uplink_settings:
                    wan_status["data"]["uplink_settings"] = uplink_settings
            except Exception as e:
                logger.debug(f"Could not get uplink settings: {e}")
            
            # Step 6: Get internet connectivity status
            try:
                internet_request = ApiRequest(
                    method="get",
                    path="/stat/wan"
                )
                internet_status = await self.connection.request(internet_request)
                if internet_status:
                    wan_status["data"]["internet_status"] = internet_status
            except Exception as e:
                logger.debug(f"Could not get internet status: {e}")
            
            # Step 7: Get routing table for WAN gateway info
            try:
                routing_request = ApiRequest(
                    method="get",
                    path="/stat/routing"
                )
                routing_info = await self.connection.request(routing_request)
                if routing_info:
                    wan_status["data"]["routing"] = routing_info
            except Exception as e:
                logger.debug(f"Could not get routing info: {e}")
            
            return wan_status
            
        except Exception as e:
            logger.error(f"Failed to get Dream Machine WAN status: {e}")
            return {"success": False, "error": str(e)}
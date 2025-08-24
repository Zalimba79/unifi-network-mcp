import logging
from typing import Dict, List, Optional, Any

from aiounifi.models.api import ApiRequest
from aiounifi.models.device import Device
from .connection_manager import ConnectionManager

logger = logging.getLogger("unifi-network-mcp")

CACHE_PREFIX_DEVICES = "devices"

class DeviceManager:
    """Manages device-related operations on the Unifi Controller."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the Device Manager.

        Args:
            connection_manager: The shared ConnectionManager instance.
        """
        self._connection = connection_manager

    async def get_devices(self) -> List[Device]:
        """Get list of devices for the current site."""
        if not await self._connection.ensure_connected() or not self._connection.controller:
            return []

        cache_key = f"{CACHE_PREFIX_DEVICES}_{self._connection.site}"
        cached_data: Optional[List[Device]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            await self._connection.controller.devices.update()
            devices: List[Device] = list(self._connection.controller.devices.values())
            self._connection._update_cache(cache_key, devices)
            return devices
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return []

    async def get_device_details(self, device_mac: str) -> Optional[Device]:
        """Get detailed information for a specific device by MAC address."""
        devices = await self.get_devices()
        device: Optional[Device] = next((d for d in devices if d.mac == device_mac), None)
        if not device:
             logger.debug(f"Device details for MAC {device_mac} not found in devices list.")
        return device

    async def reboot_device(self, device_mac: str) -> bool:
        """Reboot a device by MAC address."""
        try:
            api_request = ApiRequest(
                method="post",
                path=f"/cmd/devmgr",
                data={"mac": device_mac, "cmd": "restart"}
            )
            await self._connection.request(api_request)
            logger.info(f"Reboot command sent for device {device_mac}")
            self._connection._invalidate_cache(CACHE_PREFIX_DEVICES)
            return True
        except Exception as e:
            logger.error(f"Error rebooting device {device_mac}: {e}")
            return False

    async def rename_device(self, device_mac: str, name: str) -> bool:
        """Rename a device."""
        try:
            device = await self.get_device_details(device_mac)
            if not device or "_id" not in device.raw:
                logger.error(f"Cannot rename device {device_mac}: Not found or missing ID.")
                return False
            device_id = device.raw["_id"]

            api_request = ApiRequest(
                method="put",
                path=f"/rest/device/{device_id}",
                data={"name": name}
            )
            await self._connection.request(api_request)
            logger.info(f"Rename command sent for device {device_mac} to '{name}'")
            self._connection._invalidate_cache(CACHE_PREFIX_DEVICES)
            return True
        except Exception as e:
            logger.error(f"Error renaming device {device_mac} to '{name}': {e}")
            return False

    async def adopt_device(self, device_mac: str) -> bool:
        """Adopt a device by MAC address."""
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/devmgr",
                data={"mac": device_mac, "cmd": "adopt"}
            )
            await self._connection.request(api_request)
            logger.info(f"Adopt command sent for device {device_mac}")
            self._connection._invalidate_cache(CACHE_PREFIX_DEVICES)
            return True
        except Exception as e:
            logger.error(f"Error adopting device {device_mac}: {e}")
            return False

    async def upgrade_device(self, device_mac: str) -> bool:
        """Start firmware upgrade for a device by MAC address."""
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/devmgr",
                data={"mac": device_mac, "cmd": "upgrade"}
            )
            await self._connection.request(api_request)
            logger.info(f"Upgrade command sent for device {device_mac}")
            self._connection._invalidate_cache(CACHE_PREFIX_DEVICES)
            return True
        except Exception as e:
            logger.error(f"Error upgrading device {device_mac}: {e}")
            return False
    
    # ========== Switch Port Management Functions ==========
    
    async def get_device_port_overrides(self, device_mac: str) -> Optional[List[Dict[str, Any]]]:
        """Get current port override configurations for a device."""
        device = await self.get_device_details(device_mac)
        if not device or not hasattr(device, 'raw'):
            logger.error(f"Device {device_mac} not found or has no raw data")
            return None
        
        return device.raw.get('port_overrides', [])
    
    async def update_device_port_overrides(self, device_mac: str, port_overrides: List[Dict[str, Any]]) -> bool:
        """Update port override configurations for a device.
        
        Args:
            device_mac: MAC address of the device (switch)
            port_overrides: List of port override configurations
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            device = await self.get_device_details(device_mac)
            if not device or not hasattr(device, 'raw') or "_id" not in device.raw:
                logger.error(f"Device {device_mac} not found or missing ID")
                return False
            
            device_id = device.raw["_id"]
            
            # Prepare the update payload
            update_payload = {
                "port_overrides": port_overrides
            }
            
            api_request = ApiRequest(
                method="put",
                path=f"/rest/device/{device_id}",
                data=update_payload
            )
            
            await self._connection.request(api_request)
            logger.info(f"Port overrides updated for device {device_mac}")
            self._connection._invalidate_cache(CACHE_PREFIX_DEVICES)
            return True
            
        except Exception as e:
            logger.error(f"Error updating port overrides for device {device_mac}: {e}")
            return False
    
    async def toggle_switch_port(self, device_mac: str, port_idx: int, enabled: bool) -> bool:
        """Enable or disable a specific port on a switch.
        
        Args:
            device_mac: MAC address of the switch
            port_idx: Port index (0-based)
            enabled: True to enable, False to disable
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get current port overrides
            current_overrides = await self.get_device_port_overrides(device_mac) or []
            
            # Find or create override for this port
            port_override = None
            for override in current_overrides:
                if override.get('port_idx') == port_idx:
                    port_override = override
                    break
            
            if not port_override:
                # Create new port override
                port_override = {'port_idx': port_idx}
                current_overrides.append(port_override)
            
            # Set the forward state
            if enabled:
                # Remove 'forward' key to enable the port
                port_override.pop('forward', None)
            else:
                # Set forward to 'disabled' to disable the port
                port_override['forward'] = 'disabled'
            
            # Update the device
            return await self.update_device_port_overrides(device_mac, current_overrides)
            
        except Exception as e:
            logger.error(f"Error toggling port {port_idx} on device {device_mac}: {e}")
            return False
    
    async def set_port_poe_mode(self, device_mac: str, port_idx: int, poe_mode: str) -> bool:
        """Set PoE mode for a specific port.
        
        Args:
            device_mac: MAC address of the switch
            port_idx: Port index (0-based)
            poe_mode: PoE mode ('auto', 'passive', 'passthrough', 'off')
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get current port overrides
            current_overrides = await self.get_device_port_overrides(device_mac) or []
            
            # Find or create override for this port
            port_override = None
            for override in current_overrides:
                if override.get('port_idx') == port_idx:
                    port_override = override
                    break
            
            if not port_override:
                # Create new port override
                port_override = {'port_idx': port_idx}
                current_overrides.append(port_override)
            
            # Set the PoE mode
            port_override['poe_mode'] = poe_mode
            
            # Update the device
            return await self.update_device_port_overrides(device_mac, current_overrides)
            
        except Exception as e:
            logger.error(f"Error setting PoE mode for port {port_idx} on device {device_mac}: {e}")
            return False
    
    async def set_port_profile(self, device_mac: str, port_idx: int, portconf_id: str) -> bool:
        """Set port profile for a specific port.
        
        Args:
            device_mac: MAC address of the switch
            port_idx: Port index (0-based)
            portconf_id: Port profile ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get current port overrides
            current_overrides = await self.get_device_port_overrides(device_mac) or []
            
            # Find or create override for this port
            port_override = None
            for override in current_overrides:
                if override.get('port_idx') == port_idx:
                    port_override = override
                    break
            
            if not port_override:
                # Create new port override
                port_override = {'port_idx': port_idx}
                current_overrides.append(port_override)
            
            # Set the port profile
            port_override['portconf_id'] = portconf_id
            
            # Update the device
            return await self.update_device_port_overrides(device_mac, current_overrides)
            
        except Exception as e:
            logger.error(f"Error setting port profile for port {port_idx} on device {device_mac}: {e}")
            return False
    
    async def set_port_name(self, device_mac: str, port_idx: int, name: str) -> bool:
        """Set custom name for a specific port.
        
        Args:
            device_mac: MAC address of the switch
            port_idx: Port index (0-based)
            name: Custom name for the port
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get current port overrides
            current_overrides = await self.get_device_port_overrides(device_mac) or []
            
            # Find or create override for this port
            port_override = None
            for override in current_overrides:
                if override.get('port_idx') == port_idx:
                    port_override = override
                    break
            
            if not port_override:
                # Create new port override
                port_override = {'port_idx': port_idx}
                current_overrides.append(port_override)
            
            # Set the port name
            port_override['name'] = name
            
            # Update the device
            return await self.update_device_port_overrides(device_mac, current_overrides)
            
        except Exception as e:
            logger.error(f"Error setting name for port {port_idx} on device {device_mac}: {e}")
            return False
    
    async def get_port_profiles(self) -> List[Dict[str, Any]]:
        """Get list of available port profiles."""
        try:
            api_request = ApiRequest(
                method="get",
                path="/rest/portconf"
            )
            response = await self._connection.request(api_request)
            
            if isinstance(response, list):
                return response
            else:
                logger.warning(f"Unexpected response type for port profiles: {type(response)}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting port profiles: {e}")
            return []
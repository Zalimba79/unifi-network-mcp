import logging
from typing import Dict, List, Optional, Any

from aiounifi.models.api import ApiRequest
from aiounifi.models.wlan import Wlan
from .connection_manager import ConnectionManager

logger = logging.getLogger("unifi-network-mcp")

CACHE_PREFIX_NETWORKS = "networks"
CACHE_PREFIX_WLANS = "wlans"

class NetworkManager:
    """Manages network (LAN/VLAN) and WLAN operations on the Unifi Controller."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the Network Manager.

        Args:
            connection_manager: The shared ConnectionManager instance.
        """
        self._connection = connection_manager

    async def get_networks(self) -> List[Dict[str, Any]]:
        """Get list of networks (LAN/VLAN) for the current site."""
        cache_key = f"{CACHE_PREFIX_NETWORKS}_{self._connection.site}"
        cached_data = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            # Revert back to V1 API endpoint for listing networks
            logger.debug(f"Fetching networks using V1 endpoint /rest/networkconf")
            api_request = ApiRequest(method="get", path="/rest/networkconf")
            
            # Call the request method
            response = await self._connection.request(api_request)

            # V1 response is typically a list within a 'data' key, but aiounifi might unpack it
            # Check common patterns
            networks_data = []
            if isinstance(response, dict) and 'data' in response and isinstance(response['data'], list):
                networks_data = response['data']
            elif isinstance(response, list): # aiounifi might return the list directly
                networks_data = response
            else:
                logger.error(f"Unexpected response format from /rest/networkconf: {type(response)}. Response: {response}")
                # Don't cache potentially invalid data
                return []

            # Basic check to ensure we got a list of dicts
            if not isinstance(networks_data, list) or not all(isinstance(item, dict) for item in networks_data):
                 logger.error(f"Unexpected data structure in network list: {type(networks_data)}. Expected list of dicts. Data: {networks_data}")
                 return []
                 
            # Return the list of network dictionaries
            networks = networks_data 

            self._connection._update_cache(cache_key, networks)
            return networks
        except Exception as e:
            # Log original error for V1 endpoint failure
            logger.error(f"Error getting networks via V1 /rest/networkconf: {e}", exc_info=True)
            return []

    async def get_network_details(self, network_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific network."""
        networks = await self.get_networks()
        network = next((n for n in networks if n.get("_id") == network_id), None)
        if not network:
            logger.warning(f"Network {network_id} not found in cached/fetched list.")
        return network

    async def create_network(self, network_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new network.

        Args:
            network_data: Dictionary with network configuration

        Returns:
            The created network data if successful, None otherwise
        """
        try:
            required_fields = ["name", "purpose"] # vlan_enabled might default
            for field in required_fields:
                if field not in network_data:
                    logger.error(f"Missing required field '{field}' for network creation")
                    return None

            api_request = ApiRequest(
                method="post",
                path="/rest/networkconf",
                data=network_data
            )
            response = await self._connection.request(api_request)
            logger.info(f"Create command sent for network '{network_data.get('name')}'")
            self._connection._invalidate_cache(f"{CACHE_PREFIX_NETWORKS}_{self._connection.site}")

            if isinstance(response, dict) and "data" in response and isinstance(response["data"], list) and len(response["data"]) > 0:
                return response["data"][0]
            elif isinstance(response, list) and len(response) > 0 and isinstance(response[0], dict):
                return response[0]
            logger.warning(f"Could not extract created network data from response: {response}")
            return response # Return raw response

        except Exception as e:
            logger.error(f"Error creating network: {e}")
            return None

    async def update_network(self, network_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a network configuration by merging updates with existing data.

        Args:
            network_id: ID of the network to update
            update_data: Dictionary of fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        if not await self._connection.ensure_connected():
            return False
        if not update_data:
            logger.warning(f"No update data provided for network {network_id}.")
            return True # No action needed
            
        try:
            # 1. Fetch existing network data
            existing_network = await self.get_network_details(network_id)
            if not existing_network:
                logger.error(f"Network {network_id} not found for update.")
                return False
            
            # SECURITY CHECK: Only warn about WAN network changes
            if existing_network.get('purpose') == 'wan':
                # Just warn, don't block
                logger.warning(f"WARNING: Modifying WAN network {network_id} - Internet connectivity may be affected!")
                
            # 2. Merge updates into existing data
            merged_data = existing_network.copy()
            for key, value in update_data.items():
                merged_data[key] = value

            # 3. Send the full merged data
            api_request = ApiRequest(
                method="put",
                path=f"/rest/networkconf/{network_id}",
                data=merged_data # Send full object
            )
            await self._connection.request(api_request)
            logger.info(f"Update command sent for network {network_id} with merged data.")
            self._connection._invalidate_cache(f"{CACHE_PREFIX_NETWORKS}_{self._connection.site}")
            return True
        except Exception as e:
            logger.error(f"Error updating network {network_id}: {e}", exc_info=True)
            return False

    async def delete_network(self, network_id: str) -> bool:
        """Delete a network.
        
        SECURITY: This method now blocks deletion of WAN networks to prevent 
        accidental loss of internet connectivity!

        Args:
            network_id: ID of the network to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if this is a WAN network and warn
            networks = await self.get_networks()
            for network in networks:
                if network.id == network_id and network.purpose == 'wan':
                    logger.warning(f"WARNING: Deleting WAN network {network_id} - This may affect internet connectivity!")
                    break
            
            # Only proceed if not a WAN network
            api_request = ApiRequest(
                method="delete",
                path=f"/rest/networkconf/{network_id}"
            )
            await self._connection.request(api_request)
            logger.info(f"Delete command sent for network {network_id}")
            self._connection._invalidate_cache(f"{CACHE_PREFIX_NETWORKS}_{self._connection.site}")
            return True
        except Exception as e:
            logger.error(f"Error deleting network {network_id}: {e}")
            return False

    async def get_wlans(self) -> List[Wlan]:
        """Get list of wireless networks (WLANs) for the current site."""
        cache_key = f"{CACHE_PREFIX_WLANS}_{self._connection.site}"
        cached_data: Optional[List[Wlan]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            api_request = ApiRequest(method="get", path="/rest/wlanconf")
            response = await self._connection.request(api_request)
            wlans_data = response if isinstance(response, list) else []
            wlans: List[Wlan] = [Wlan(raw_wlan) for raw_wlan in wlans_data]
            self._connection._update_cache(cache_key, wlans)
            return wlans
        except Exception as e:
            logger.error(f"Error getting WLANs: {e}")
            return []

    async def get_wlan_details(self, wlan_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific wireless network as a dictionary."""
        wlans = await self.get_wlans()
        wlan_obj: Optional[Wlan] = next((w for w in wlans if w.id == wlan_id), None)
        if not wlan_obj:
            logger.warning(f"WLAN {wlan_id} not found in cached/fetched list.")
            return None
        # Return the raw dictionary
        return wlan_obj.raw if hasattr(wlan_obj, 'raw') else None

    async def create_wlan(self, wlan_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new wireless network. Returns the created WLAN data dict or None."""
        try:
            required_fields = ["name", "security", "enabled"] # x_passphrase needed depending on security
            for field in required_fields:
                if field not in wlan_data:
                    logger.error(f"Missing required field '{field}' for WLAN creation")
                    return None
            if wlan_data.get("security") != "open" and "x_passphrase" not in wlan_data:
                 logger.error(f"Missing required field 'x_passphrase' for WLAN security type '{wlan_data.get("security")}'")
                 return None
            
            # Set default values based on UniFi API requirements
            wlan_data.setdefault("usergroup_id", "")
            wlan_data.setdefault("wlangroup_id", "")  
            wlan_data.setdefault("hide_ssid", False)
            wlan_data.setdefault("is_guest", False)
            wlan_data.setdefault("wpa_mode", "wpa2")
            wlan_data.setdefault("wpa_enc", "ccmp")
            wlan_data.setdefault("uapsd_enabled", False)
            wlan_data.setdefault("schedule_enabled", False)
            wlan_data.setdefault("schedule", [])
            # CRITICAL: UniFi requires ap_group_ids to be set!
            wlan_data.setdefault("ap_group_ids", [])  # Empty list = all APs

            # Note: Using /rest/wlanconf for creation (aiounifi doesn't support /add/wlanconf)
            # The critical fix was adding ap_group_ids parameter
            api_request = ApiRequest(
                method="post",
                path="/rest/wlanconf",
                data=wlan_data
            )
            response = await self._connection.request(api_request)
            logger.info(f"Create command sent for WLAN '{wlan_data.get('name')}'")
            self._connection._invalidate_cache(f"{CACHE_PREFIX_WLANS}_{self._connection.site}")

            # Check if response is None or empty
            if response is None:
                logger.error("Response is None - API might have returned empty response")
                return None
            
            logger.debug(f"WLAN creation response type: {type(response)}")
            logger.debug(f"WLAN creation response: {response}")

            created_wlan_data = None
            # The response from connection.request() already has 'data' extracted (line 171)
            # So response IS the data, not wrapped in {"data": ...}
            if isinstance(response, list) and len(response) > 0 and isinstance(response[0], dict):
                created_wlan_data = response[0]
            elif isinstance(response, dict) and response.get("_id"):
                # Sometimes UniFi returns a single dict directly
                created_wlan_data = response
            elif isinstance(response, dict) and "data" in response and isinstance(response["data"], list) and len(response["data"]) > 0:
                # Fallback for wrapped response
                created_wlan_data = response["data"][0]

            if created_wlan_data and isinstance(created_wlan_data, dict):
                logger.info(f"Successfully extracted WLAN data with ID: {created_wlan_data.get('_id')}")
                return created_wlan_data
            
            logger.warning(f"Could not extract created WLAN data from response: {response}")
            # Return raw response or None if it wasn't useful
            return created_wlan_data if isinstance(created_wlan_data, dict) else None 

        except Exception as e:
            logger.error(f"Error creating WLAN: {e}", exc_info=True)
            logger.error(f"WLAN data sent: {wlan_data}")
            return None # Return None on error

    async def update_wlan(self, wlan_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a WLAN configuration by merging updates with existing data.

        Args:
            wlan_id: ID of the WLAN to update
            update_data: Dictionary of fields to update

        Returns:
            bool: True if successful, False otherwise
        """
        if not await self._connection.ensure_connected():
            return False
        if not update_data:
            logger.warning(f"No update data provided for WLAN {wlan_id}.")
            return True # No action needed
            
        try:
            # 1. Fetch existing WLAN data
            existing_wlan = await self.get_wlan_details(wlan_id) # Changed to use detail method
            if not existing_wlan:
                logger.error(f"WLAN {wlan_id} not found for update.")
                return False

            # 2. Merge updates
            merged_data = existing_wlan.copy()
            for key, value in update_data.items():
                merged_data[key] = value
                
            # Ensure required fields from original object are preserved if not updated
            # (The API might require certain fields even on update)
            # Example: might need 'name', 'security' etc. even if not changing them.
            # This is handled by starting with existing_wlan.copy()

            # 3. Send the full merged data
            api_request = ApiRequest(
                method="put",
                path=f"/rest/wlanconf/{wlan_id}",
                data=merged_data # Send full object
            )
            await self._connection.request(api_request)
            logger.info(f"Update command sent for WLAN {wlan_id} with merged data.")
            self._connection._invalidate_cache(f"{CACHE_PREFIX_WLANS}_{self._connection.site}")
            return True
        except Exception as e:
            logger.error(f"Error updating WLAN {wlan_id}: {e}", exc_info=True)
            return False

    async def delete_wlan(self, wlan_id: str) -> bool:
        """Delete a wireless network.

        Args:
            wlan_id: ID of the WLAN to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            api_request = ApiRequest(
                method="delete",
                path=f"/rest/wlanconf/{wlan_id}"
            )
            await self._connection.request(api_request)
            logger.info(f"Delete command sent for WLAN {wlan_id}")
            self._connection._invalidate_cache(f"{CACHE_PREFIX_WLANS}_{self._connection.site}")
            return True
        except Exception as e:
            logger.error(f"Error deleting WLAN {wlan_id}: {e}")
            return False

    async def toggle_wlan(self, wlan_id: str) -> bool:
        """Toggle a wireless network on/off.

        Args:
            wlan_id: ID of the WLAN to toggle

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            wlan = await self.get_wlan_details(wlan_id)
            if not wlan:
                logger.error(f"Cannot toggle WLAN {wlan_id}: Not found.")
                return False

            new_state = not wlan.enabled
            update_payload = {"enabled": new_state}

            api_request = ApiRequest(
                method="put",
                path=f"/rest/wlanconf/{wlan_id}",
                data=update_payload
            )
            await self._connection.request(api_request)
            logger.info(f"Toggle command sent for WLAN {wlan_id} (new state: {'enabled' if new_state else 'disabled'})")
            self._connection._invalidate_cache(f"{CACHE_PREFIX_WLANS}_{self._connection.site}")
            return True
        except Exception as e:
            logger.error(f"Error toggling WLAN {wlan_id}: {e}")
            return False
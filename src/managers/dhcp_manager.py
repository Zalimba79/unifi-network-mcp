"""DHCP Manager for handling fixed IP reservations and DHCP-related operations."""

from typing import Dict, List, Any, Optional
from aiounifi.models.api import ApiRequest
import logging

logger = logging.getLogger(__name__)


class DHCPManager:
    """Manager for DHCP reservations and fixed IP assignments."""
    
    def __init__(self, connection):
        """Initialize DHCP manager with connection."""
        self.connection = connection
        
    async def list_dhcp_reservations(self) -> List[Dict[str, Any]]:
        """
        List all DHCP reservations (fixed IP assignments) across all networks.
        
        Returns:
            List of DHCP reservations with client and network information
        """
        await self.connection.ensure_connected()
        
        # Get all clients with fixed IPs
        clients_with_fixed_ip = []
        
        # Get all clients
        clients = self.connection.controller.clients.values()
        
        for client in clients:
            # Check if client has fixed IP configuration
            if hasattr(client, 'use_fixedip') and client.use_fixedip:
                reservation = {
                    '_id': client.id,
                    'mac': client.mac,
                    'name': getattr(client, 'name', getattr(client, 'hostname', 'Unknown')),
                    'fixed_ip': getattr(client, 'fixed_ip', None),
                    'network_id': getattr(client, 'network_id', None),
                    'use_fixedip': True,
                    'noted': getattr(client, 'noted', False),
                    'blocked': getattr(client, 'blocked', False)
                }
                
                # Try to get network name
                if reservation['network_id']:
                    try:
                        networks = await self.connection.controller.request(
                            ApiRequest(
                                method="get",
                                path="/rest/networkconf",
                                data={}
                            )
                        )
                        for network in networks:
                            if network.get('_id') == reservation['network_id']:
                                reservation['network_name'] = network.get('name', 'Unknown')
                                reservation['network_subnet'] = network.get('ip_subnet', '')
                                break
                    except Exception as e:
                        logger.warning(f"Could not fetch network info: {e}")
                
                clients_with_fixed_ip.append(reservation)
        
        return clients_with_fixed_ip
    
    async def set_client_fixed_ip(
        self,
        client_mac: str,
        fixed_ip: str,
        network_id: Optional[str] = None,
        use_fixedip: bool = True
    ) -> bool:
        """
        Set or update a fixed IP reservation for a client.
        
        Args:
            client_mac: MAC address of the client
            fixed_ip: The fixed IP address to assign
            network_id: The network ID where the IP belongs (optional, uses default if not specified)
            use_fixedip: Enable or disable fixed IP (default: True)
            
        Returns:
            True if successful, False otherwise
        """
        await self.connection.ensure_connected()
        
        # Find the client by MAC
        client = None
        for c in self.connection.controller.clients.values():
            if c.mac.lower() == client_mac.lower():
                client = c
                break
        
        if not client:
            logger.error(f"Client with MAC {client_mac} not found")
            return False
        
        # If network_id not specified, try to determine it from the IP
        if not network_id and use_fixedip:
            networks = await self.connection.controller.request(
                ApiRequest(
                    method="get",
                    path="/rest/networkconf",
                    data={}
                )
            )
            
            # Find matching network based on IP subnet
            import ipaddress
            target_ip = ipaddress.ip_address(fixed_ip)
            
            for network in networks:
                subnet = network.get('ip_subnet')
                if subnet:
                    try:
                        network_obj = ipaddress.ip_network(subnet)
                        if target_ip in network_obj:
                            network_id = network['_id']
                            logger.info(f"Auto-detected network {network.get('name')} for IP {fixed_ip}")
                            break
                    except Exception:
                        continue
            
            if not network_id:
                logger.error(f"Could not determine network for IP {fixed_ip}")
                return False
        
        # Prepare the update data
        update_data = {
            '_id': client.id,
            'use_fixedip': use_fixedip
        }
        
        if use_fixedip:
            update_data['fixed_ip'] = fixed_ip
            update_data['network_id'] = network_id
        
        # Update the client
        try:
            await self.connection.controller.request(
                ApiRequest(
                    method="put",
                    path=f"/rest/user/{client.id}",
                    data=update_data
                )
            )
            
            logger.info(f"Successfully set fixed IP {fixed_ip} for client {client_mac}")
            self.connection._invalidate_cache()
            return True
            
        except Exception as e:
            logger.error(f"Failed to set fixed IP for client {client_mac}: {e}")
            return False
    
    async def remove_client_fixed_ip(self, client_mac: str) -> bool:
        """
        Remove fixed IP reservation for a client (enable DHCP).
        
        Args:
            client_mac: MAC address of the client
            
        Returns:
            True if successful, False otherwise
        """
        return await self.set_client_fixed_ip(client_mac, "", None, False)
    
    async def get_client_fixed_ip(self, client_mac: str) -> Optional[Dict[str, Any]]:
        """
        Get fixed IP configuration for a specific client.
        
        Args:
            client_mac: MAC address of the client
            
        Returns:
            Fixed IP configuration or None if not found
        """
        await self.connection.ensure_connected()
        
        for client in self.connection.controller.clients.values():
            if client.mac.lower() == client_mac.lower():
                if hasattr(client, 'use_fixedip') and client.use_fixedip:
                    return {
                        '_id': client.id,
                        'mac': client.mac,
                        'name': getattr(client, 'name', getattr(client, 'hostname', 'Unknown')),
                        'fixed_ip': getattr(client, 'fixed_ip', None),
                        'network_id': getattr(client, 'network_id', None),
                        'use_fixedip': True
                    }
                return None
        
        return None
    
    async def create_dhcp_reservation(
        self,
        mac_address: str,
        fixed_ip: str,
        name: Optional[str] = None,
        network_id: Optional[str] = None
    ) -> bool:
        """
        Create a new DHCP reservation for a device that may not be online yet.
        
        Args:
            mac_address: MAC address of the device
            fixed_ip: The fixed IP to assign
            name: Optional name for the device
            network_id: Optional network ID (auto-detected if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        await self.connection.ensure_connected()
        
        # Auto-detect network if not provided
        if not network_id:
            networks = await self.connection.controller.request(
                ApiRequest(
                    method="get",
                    path="/rest/networkconf",
                    data={}
                )
            )
            
            import ipaddress
            target_ip = ipaddress.ip_address(fixed_ip)
            
            for network in networks:
                subnet = network.get('ip_subnet')
                if subnet:
                    try:
                        network_obj = ipaddress.ip_network(subnet)
                        if target_ip in network_obj:
                            network_id = network['_id']
                            break
                    except Exception:
                        continue
        
        if not network_id:
            logger.error(f"Could not determine network for IP {fixed_ip}")
            return False
        
        # Create a new user/client entry with fixed IP
        user_data = {
            'mac': mac_address.lower(),
            'use_fixedip': True,
            'fixed_ip': fixed_ip,
            'network_id': network_id
        }
        
        if name:
            user_data['name'] = name
            user_data['noted'] = True
        
        try:
            await self.connection.controller.request(
                ApiRequest(
                    method="post",
                    path="/rest/user",
                    data=user_data
                )
            )
            
            logger.info(f"Successfully created DHCP reservation for {mac_address} with IP {fixed_ip}")
            self.connection._invalidate_cache()
            return True
            
        except Exception as e:
            logger.error(f"Failed to create DHCP reservation: {e}")
            return False
    
    async def list_available_ips(self, network_id: str) -> List[str]:
        """
        List available IP addresses in a network that are not reserved.
        
        Args:
            network_id: The network ID to check
            
        Returns:
            List of available IP addresses
        """
        await self.connection.ensure_connected()
        
        # Get network configuration
        networks = await self.connection.controller.request(
            ApiRequest(
                method="get",
                path="/rest/networkconf",
                data={}
            )
        )
        
        network_config = None
        for network in networks:
            if network.get('_id') == network_id:
                network_config = network
                break
        
        if not network_config:
            logger.error(f"Network {network_id} not found")
            return []
        
        import ipaddress
        
        # Get the network subnet
        subnet = network_config.get('ip_subnet')
        if not subnet:
            return []
        
        network_obj = ipaddress.ip_network(subnet)
        
        # Get DHCP range
        dhcp_start = network_config.get('dhcpd_start')
        dhcp_stop = network_config.get('dhcpd_stop')
        
        if not dhcp_start or not dhcp_stop:
            return []
        
        start_ip = ipaddress.ip_address(dhcp_start)
        stop_ip = ipaddress.ip_address(dhcp_stop)
        
        # Get all reserved IPs
        reservations = await self.list_dhcp_reservations()
        reserved_ips = set(r['fixed_ip'] for r in reservations if r.get('fixed_ip'))
        
        # Get all active client IPs
        active_ips = set()
        for client in self.connection.controller.clients.values():
            if hasattr(client, 'ip'):
                active_ips.add(client.ip)
        
        # Find available IPs in DHCP range
        available = []
        current_ip = start_ip
        while current_ip <= stop_ip:
            ip_str = str(current_ip)
            if ip_str not in reserved_ips and ip_str not in active_ips:
                available.append(ip_str)
            current_ip += 1
        
        return available[:50]  # Limit to 50 to avoid huge lists
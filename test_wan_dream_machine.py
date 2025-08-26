#!/usr/bin/env python3
"""Test script to verify WAN information extraction for Dream Machine Pro."""

import asyncio
import logging
import json
from src.runtime import connection_manager
from src.managers.wan_manager import WANManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_wan_extraction():
    """Test the enhanced WAN information extraction."""
    try:
        # Ensure connection
        await connection_manager.ensure_connected()
        
        print("\n=== TESTING WAN INFORMATION EXTRACTION ===\n")
        
        # Create WAN manager
        wan_manager = WANManager(connection_manager)
        
        # Test 1: Get standard WAN configuration (enhanced version)
        print("1. Testing enhanced get_wan_configuration()...")
        print("-" * 50)
        wan_config = await wan_manager.get_wan_configuration()
        
        if wan_config.get("success"):
            print(f"Source: {wan_config.get('source', 'unknown')}")
            print(f"Gateway Model: {wan_config.get('gateway_model', 'Not found')}")
            print(f"Gateway MAC: {wan_config.get('gateway_mac', 'Not found')}")
            
            # WAN interfaces
            interfaces = wan_config.get("wan_interfaces", [])
            if interfaces:
                print(f"\nWAN Interfaces ({len(interfaces)}):")
                for iface in interfaces:
                    print(f"  - {iface.get('name')}: IP={iface.get('ip', 'N/A')}, Type={iface.get('type')}")
            else:
                print("No WAN interfaces found in standard config")
            
            # WAN health info (from health endpoint)
            if "wan_health" in wan_config:
                health = wan_config["wan_health"]
                print(f"\nWAN Health Info:")
                print(f"  Status: {health.get('status')}")
                print(f"  WAN IP: {health.get('wan_ip')}")
                print(f"  Gateway: {health.get('gw_name')} ({health.get('gw_mac')})")
                print(f"  Uptime: {health.get('uptime')} seconds")
                print(f"  Latency: {health.get('latency')} ms")
                if health.get('speedtest_lastrun'):
                    print(f"  Last Speed Test: {health.get('speedtest_lastrun')}")
                    print(f"  Speed Test Ping: {health.get('speedtest_ping')} ms")
            
            # WAN network config
            if "wan_network" in wan_config:
                net = wan_config["wan_network"]
                print(f"\nWAN Network Configuration:")
                print(f"  Name: {net.get('name')}")
                print(f"  Type: {net.get('wan_type')}")
                if net.get('wan_ip'):
                    print(f"  Static IP: {net.get('wan_ip')}")
                    print(f"  Gateway: {net.get('wan_gateway')}")
                    print(f"  DNS1: {net.get('wan_dns1')}")
                    print(f"  DNS2: {net.get('wan_dns2')}")
        else:
            print(f"Failed to get WAN config: {wan_config.get('error')}")
        
        print("\n" + "=" * 50)
        
        # Test 2: Get Dream Machine specific WAN status
        print("\n2. Testing get_dream_machine_wan_status()...")
        print("-" * 50)
        dm_status = await wan_manager.get_dream_machine_wan_status()
        
        if dm_status.get("success"):
            if dm_status.get("is_dream_machine"):
                print("✓ This IS a Dream Machine!")
                data = dm_status.get("data", {})
                
                # Controller info
                if "controller" in data:
                    ctrl = data["controller"]
                    print(f"\nController Details:")
                    print(f"  Model: {ctrl.get('model')}")
                    print(f"  Version: {ctrl.get('version')}")
                    print(f"  Hostname: {ctrl.get('hostname')}")
                    print(f"  MAC: {ctrl.get('mac')}")
                
                # Health subsystem
                if "health" in data:
                    health = data["health"]
                    print(f"\nWAN Health Subsystem:")
                    print(f"  Status: {health.get('status')}")
                    print(f"  WAN IP: {health.get('wan_ip')}")
                    print(f"  Uptime: {health.get('uptime')} seconds")
                    print(f"  Gateway MAC: {health.get('gw_mac')}")
                
                # Device stats
                if "device_stats" in data:
                    print(f"\nDevice Stats: Available")
                
                # Port configs
                if "port_configs" in data:
                    print(f"\nPort Configs: {len(data['port_configs'])} profiles found")
                
                # Uplink settings
                if "uplink_settings" in data:
                    print(f"\nUplink Settings: Available")
                
                # Internet status
                if "internet_status" in data:
                    print(f"\nInternet Status: Available")
                    
                # Routing info
                if "routing" in data:
                    print(f"\nRouting Info: Available")
                
                # Print full data for debugging
                print(f"\n\nFull Dream Machine WAN Data (JSON):")
                print("=" * 50)
                print(json.dumps(dm_status, indent=2, default=str))
            else:
                print(f"Not a Dream Machine: {dm_status.get('error')}")
        else:
            print(f"Failed to get Dream Machine status: {dm_status.get('error')}")
        
        print("\n" + "=" * 50)
        print("\n✓ WAN information extraction test complete!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_wan_extraction())
#!/usr/bin/env python3
"""Debug script to find the Dream Machine Pro in the device list."""

import asyncio
import logging
from src.runtime import connection_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def find_gateway():
    """Find and debug the gateway device."""
    try:
        # Ensure connection
        await connection_manager.ensure_connected()
        
        print("\n=== SEARCHING FOR GATEWAY DEVICE ===\n")
        
        # Get all devices
        devices = connection_manager.controller.devices.values()
        
        print(f"Total devices found: {len(devices)}")
        print("-" * 50)
        
        # Check each device
        for device in devices:
            print(f"\nDevice: {device.name if hasattr(device, 'name') else 'Unknown'}")
            print(f"  MAC: {device.mac}")
            print(f"  Type: {device.type if hasattr(device, 'type') else 'NO TYPE'}")
            print(f"  Model: {device.model if hasattr(device, 'model') else 'NO MODEL'}")
            
            # Check if it could be a gateway
            if hasattr(device, 'type'):
                device_type = device.type.lower()
                if any(gw in device_type for gw in ['gateway', 'dream', 'udm', 'ugw', 'uxg']):
                    print(f"  *** POTENTIAL GATEWAY DETECTED ***")
            
            # Check for WAN attributes
            if hasattr(device, 'wan1') or hasattr(device, 'wan2'):
                print(f"  *** HAS WAN INTERFACES ***")
            
            # Check specific MAC
            if device.mac.lower() == "78:45:58:c1:36:fb".lower():
                print(f"  *** THIS IS THE DREAM MACHINE PRO FROM HEALTH STATUS ***")
                print(f"  Full device attributes: {dir(device)}")
                if hasattr(device, 'raw'):
                    print(f"  Raw data type: {device.raw.get('type') if isinstance(device.raw, dict) else 'Not a dict'}")
        
        print("\n" + "=" * 50)
        
        # Also check system info
        from aiounifi.models.api import ApiRequest
        api_request = ApiRequest(
            method="get",
            path="/stat/sysinfo"
        )
        sysinfo = await connection_manager.request(api_request)
        
        if sysinfo:
            print("\n=== SYSTEM INFO ===")
            print(f"System Model: {sysinfo.get('model', 'Unknown')}")
            print(f"System Version: {sysinfo.get('version', 'Unknown')}")
            if 'dream' in str(sysinfo.get('model', '')).lower():
                print("*** System IS a Dream Machine! ***")
                
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(find_gateway())
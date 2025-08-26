"""
Firewall policy tools for Unifi Network MCP server.
"""

import logging
import json
from typing import Dict, List, Any, Optional

from src.runtime import server, config, firewall_manager
from src.runtime import network_manager
import mcp.types as types # Import the types module
from src.utils.permissions import parse_permission # CORRECTED import name
from src.validator_registry import UniFiValidatorRegistry # Added

logger = logging.getLogger(__name__)

# FIREWALL CREATION FLAG
# Set to False because UniFi V2 API firewall CREATION is broken
# List, toggle, and update still work fine!
# When UniFi fixes their API, set this to True to re-enable creation tools
FIREWALL_CREATE_ENABLED = False 

@server.tool(
    name="unifi_list_firewall_policies",
    description="List firewall policies configured on the Unifi Network controller."
)
async def list_firewall_policies(
    include_predefined: bool = False
) -> Dict[str, Any]:
    """
    Lists firewall policies for the current UniFi site.

    Args:
        include_predefined (bool): Whether to include predefined system policies (default: False).

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - site (str): The identifier of the UniFi site queried.
        - count (int): The number of firewall policies found.
        - policies (List[Dict]): A list of firewall policies, each containing summary info:
            - id (str): The unique identifier (_id) of the policy.
            - name (str): The user-defined name of the policy.
            - enabled (bool): Whether the policy is currently active.
            - action (str): The policy action (e.g., 'accept', 'drop', 'reject').
            - rule_index (int): The order/index of the rule within its ruleset.
            - ruleset (str): The ruleset this policy belongs to (e.g., 'WAN_IN', 'LAN_OUT').
            - description (str): User-provided description of the policy.
        - error (str, optional): An error message if the operation failed.

    Example response (success):
    {
        "success": True,
        "site": "default",
        "count": 1,
        "policies": [
            {
                "id": "60b8a7f1e4b0f4a7f7d6e8c0",
                "name": "Allow Established/Related",
                "enabled": True,
                "action": "accept",
                "rule_index": 2000,
                "ruleset": "WAN_IN",
                "description": "Allow established and related sessions"
            }
        ]
    }
    """
    if not parse_permission(config.permissions, "firewall", "read"):
        logger.warning(f"Permission denied for listing firewall policies.")
        return {"success": False, "error": "Permission denied to list firewall policies."}

    try:
        policies = await firewall_manager.get_firewall_policies(include_predefined=include_predefined)
        policies_raw = [p.raw if hasattr(p, "raw") else p for p in policies]

        formatted_policies = [
            {
                "id": p.get("_id"),
                "name": p.get("name"),
                "enabled": p.get("enabled"),
                "action": p.get("action"),
                "rule_index": p.get("index", p.get("rule_index")),
                "ruleset": p.get("ruleset"),
                "description": p.get("description", p.get("desc", ""))
            }
            for p in policies_raw
        ]
        return {
            "success": True, "site": firewall_manager._connection.site,
            "count": len(formatted_policies), "policies": formatted_policies
        }
    except Exception as e:
        logger.error(f"Error listing firewall policies: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
     name="unifi_get_firewall_policy_details",
     description="Get detailed configuration for a specific firewall policy by ID."
)
async def get_firewall_policy_details(
    policy_id: str
) -> Dict[str, Any]:
    """
    Gets the detailed configuration of a specific firewall policy by its ID.

    Args:
        policy_id (str): The unique identifier (_id) of the firewall policy.

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - policy_id (str): The ID of the policy requested.
        - details (Dict[str, Any]): A dictionary containing the raw configuration details
          of the firewall policy as returned by the UniFi controller.
        - error (str, optional): An error message if the operation failed (e.g., policy not found).

    Example response (success):
    {
        "success": True,
        "policy_id": "60b8a7f1e4b0f4a7f7d6e8c0",
        "details": {
            "_id": "60b8a7f1e4b0f4a7f7d6e8c0",
            "name": "Allow Established/Related",
            "enabled": True,
            "action": "accept",
            "rule_index": 2000,
            "ruleset": "WAN_IN",
            "description": "Allow established and related sessions",
            "protocol_match_excepted": False,
            "logging": False,
            "state_established": True,
            "state_invalid": False,
            "state_new": False,
            "state_related": True,
            "site_id": "...",
            # ... other fields
        }
    }
    """
    if not parse_permission(config.permissions, "firewall", "read"):
        logger.warning(f"Permission denied for getting firewall policy details ({policy_id}).")
        return {"success": False, "error": "Permission denied to get firewall policy details."}

    try:
        if not policy_id:
             return {"success": False, "error": "policy_id is required"}
        policies = await firewall_manager.get_firewall_policies(include_predefined=True)
        policies_raw = [p.raw if hasattr(p, "raw") else p for p in policies]
        policy = next((p for p in policies_raw if p.get("_id") == policy_id), None)
        if not policy:
            return {"success": False, "error": f"Firewall policy with ID '{policy_id}' not found."}
        return {"success": True, "policy_id": policy_id, "details": json.loads(json.dumps(policy, default=str))} 
    except Exception as e:
        logger.error(f"Error getting firewall policy details for {policy_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_toggle_firewall_policy",
    description="Enable or disable a specific firewall policy by ID."
)
async def toggle_firewall_policy(
    policy_id: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Enables or disables a specific firewall policy. Requires confirmation.

    Args:
        policy_id (str): The unique identifier (_id) of the firewall policy to toggle.
        confirm (bool): Must be explicitly set to `True` to execute the toggle operation. Defaults to `False`.

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - policy_id (str): The ID of the policy toggled.
        - enabled (bool): The new state of the policy (True if enabled, False if disabled).
        - message (str): A confirmation message indicating the action taken.
        - error (str, optional): An error message if the operation failed.

    Example response (success):
    {
        "success": True,
        "policy_id": "60b8a7f1e4b0f4a7f7d6e8c0",
        "enabled": false,
        "message": "Firewall policy 'Allow Established/Related' (60b8a7f1e4b0f4a7f7d6e8c0) toggled to disabled."
    }
    """
    if not parse_permission(config.permissions, "firewall", "update"):
        logger.warning(f"Permission denied for toggling firewall policy ({policy_id}).")
        return {"success": False, "error": "Permission denied to toggle firewall policy."}

    if not confirm:
        logger.warning(f"Confirmation missing for toggling policy {policy_id}.")
        return {"success": False, "error": "Confirmation required to toggle policy. Set 'confirm' to true."}
    
    try:
        policies = await firewall_manager.get_firewall_policies(include_predefined=True)
        policy_obj = next((p for p in policies if p.id == policy_id), None)
        if not policy_obj or not policy_obj.raw:
            return {"success": False, "error": f"Firewall policy with ID '{policy_id}' not found."}
        policy = policy_obj.raw

        current_state = policy.get("enabled", False)
        policy_name = policy.get("name", policy_id)
        new_state = not current_state

        logger.info(f"Attempting to toggle firewall policy '{policy_name}' ({policy_id}) to {new_state}")

        success = await firewall_manager.toggle_firewall_policy(policy_id)
        
        if success:
            toggled_policy_obj = next((p for p in await firewall_manager.get_firewall_policies(include_predefined=True) if p.id == policy_id), None)
            final_state = toggled_policy_obj.enabled if toggled_policy_obj else new_state
            
            logger.info(f"Successfully toggled firewall policy '{policy_name}' ({policy_id}) to {final_state}")
            return {
                "success": True,
                "policy_id": policy_id,
                "enabled": final_state,
                "message": f"Firewall policy '{policy_name}' ({policy_id}) toggled successfully to {'enabled' if final_state else 'disabled'}."
            }
        else:
            logger.error(f"Failed to toggle firewall policy '{policy_name}' ({policy_id}). Manager returned false.")
            policy_after_toggle_obj = next((p for p in await firewall_manager.get_firewall_policies(include_predefined=True) if p.id == policy_id), None)
            state_after = policy_after_toggle_obj.enabled if policy_after_toggle_obj else "unknown"
            return {
                "success": False,
                "policy_id": policy_id,
                "state_after_attempt": state_after,
                "error": f"Failed to toggle firewall policy '{policy_name}' ({policy_id}). Check server logs."
            }
    except Exception as e:
        logger.error(f"Error toggling firewall policy {policy_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

# Firewall creation is BROKEN - not registered as tool
async def create_firewall_policy(
    policy_data: Dict[str, Any]
) -> Dict[str, Any]:
    """⚠️ WARNING: THIS FUNCTION DOES NOT WORK DUE TO UniFi API LIMITATIONS!
    
    The UniFi Controller V2 Firewall API has bugs that prevent reliable rule creation.
    This is NOT a bug in our code but a limitation of the UniFi API itself.
    
    WORKING ALTERNATIVES:
    - Enable "Network Isolation" in VLAN settings for inter-VLAN blocking
    - Use Traffic Routes (unifi_create_traffic_route) for routing rules  
    - Configure port isolation at switch level
    - Create rules manually in UniFi Web UI
    
    Original documentation:
    Creates a new firewall policy based on the provided configuration data.
    This tool performs validation on the input data against the expected UniFi API schema.

    **Crucial Note:** The structure of `policy_data` needs to match the UniFi controller's
    expectations for the V2 `/firewall-policies` endpoint. Refer to UniFi documentation
    or examine existing policies using `unifi_get_firewall_policy_details` for the exact structure.

    **Required** keys in `policy_data`:
    - name (string): A descriptive name for the firewall policy.
    - ruleset (string): The target ruleset (e.g., "WAN_IN", "LAN_OUT", "GUEST_LOCAL").
    - action (string): The action to take (must be lowercase: "accept", "drop", "reject").
    - index (integer): The position/priority of the rule within the ruleset (lower numbers execute first).
                       Note: API internally uses 'index', not 'rule_index'.

    **Common Optional** keys in `policy_data`:
    - enabled (boolean): Whether the rule is active upon creation (default: True).
    - description (string): A brief description of the rule's purpose.
    - logging (boolean): Enable logging for matched traffic (default: False).
    - protocol (string): Network protocol ("tcp", "udp", "icmp", "all", etc.).
    - connection_states (list[string]): Connection states to match (e.g., ["new", "established", "related"]).
    - source (dict): Source definition (see UniFi structure - often includes `zone_id`, `matching_target`, etc.).
    - destination (dict): Destination definition (see UniFi structure).
    - icmp_typename (string): Specific ICMP type name (if protocol is "icmp").
    - icmp_v6_typename (string): Specific ICMPv6 type name (if protocol is "icmpv6").
    - ... and other fields specific to the UniFi API.

    Example `policy_data` (Simple Block):
    {
        "name": "Block Xbox LAN Out",
        "ruleset": "LAN_OUT",
        "action": "drop",
        "index": 2010,
        "enabled": True,
        "logging": True,
        "description": "Block specific Xbox device from WAN",
        "source": {
            "match_opposite_ports": False,
            "matching_target": "client_macs",
            "port_matching_type": "any",
            "zone_id": "trusted", # Replace with actual source zone ID if needed
            "client_macs": ["4c:3b:df:2c:c8:c6"] # Example MAC
        },
        "destination": {
            "match_opposite_ports": False,
            "matching_target": "zone",
            "port_matching_type": "any",
            "zone_id": "wan" # Target the WAN zone
        },
        "protocol": "all",
        "connection_state_type": "inclusive",
        "connection_states": ["new", "established", "related", "invalid"], # Block all states
        "ip_version": "ipv4" # Or "ipv6" or "both"
    }

    Returns:
        A dictionary containing:
        - success (boolean): Whether the operation succeeded.
        - message (string): Confirmation message on success.
        - policy_id (string): The ID (_id) of the newly created policy if successful.
        - details (Dict): Full details of the created policy as returned by the controller.
        - error (string): Error message if unsuccessful (includes validation errors or API errors).
    """
    # IMMEDIATELY RETURN ERROR WITH ALTERNATIVES
    return {
        "success": False,
        "error": "Firewall creation is NON-FUNCTIONAL due to UniFi API limitations",
        "message": "The UniFi V2 Firewall API is broken. Please use these working alternatives:",
        "alternatives": {
            "network_isolation": "Enable in Settings → Networks → [VLAN] → Network Isolation",
            "traffic_routes": "Use unifi_create_traffic_route tool (fully functional)",
            "port_isolation": "Use unifi_toggle_switch_port for port-level isolation",
            "manual": "Create rules in UniFi Web UI at Settings → Firewall & Security"
        },
        "technical_details": "UniFi V2 API at /v2/api/site/default/firewall-policies has incomplete implementation"
    }

@server.tool(
    name="unifi_update_firewall_policy",
    description="Update specific fields of an existing firewall policy by ID."
)
async def update_firewall_policy(
    policy_id: str,
    update_data: Dict[str, Any],
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Updates specific fields of an existing firewall policy. Requires confirmation.

    Allows modifying properties like name, action, enabled state, rule index, 
    protocol, addresses, ports, etc. Only provided fields are updated.

    Args:
        policy_id (str): The unique identifier (_id) of the firewall policy to update.
        update_data (Dict[str, Any]): A dictionary containing the fields to update.
            Allowed fields (all optional):
            - name (string): New name for the policy.
            - ruleset (string): Move to a different ruleset (e.g., "WAN_IN").
            - action (string): New action ("accept", "drop", "reject").
            - rule_index (integer): New position index.
            - protocol (string): New protocol ("tcp", "udp", "icmp", "all").
            - src_address (string): New source IP/CIDR.
            - dst_address (string): New destination IP/CIDR.
            - src_port (string): New source port/range.
            - dst_port (string): New destination port/range.
            - enabled (boolean): New enabled state.
            - description (string): New description.
            - state_new (boolean): New state matching.
            - state_established (boolean): New state matching.
            - state_related (boolean): New state matching.
            - state_invalid (boolean): New state matching.
            - logging (boolean): New logging state.
        confirm (bool): Must be explicitly set to `True` to execute the update. Defaults to `False`.

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - policy_id (str): The ID of the policy that was updated.
        - updated_fields (List[str]): Field names that were successfully updated.
        - details (Dict[str, Any]): Full details of the policy after the update.
        - error (str, optional): Error message if the operation failed.

    Example call:
    update_firewall_policy(
        policy_id="60b8a7f1e4b0f4a7f7d6e8c0",
        update_data={
            "name": "Allow Established - Updated",
            "enabled": False,
            "logging": True
        },
        confirm=True
    )

    Example response (success):
    {
        "success": True,
        "policy_id": "60b8a7f1e4b0f4a7f7d6e8c0",
        "updated_fields": ["name", "enabled", "logging"],
        "details": { ... updated policy details ... }
    }
    """
    if not parse_permission(config.permissions, "firewall", "update"):
        logger.warning(f"Permission denied for updating firewall policy ({policy_id}).")
        return {"success": False, "error": "Permission denied to update firewall policy."}

    if not confirm:
        logger.warning(f"Confirmation missing for updating policy {policy_id}.")
        return {"success": False, "error": "Confirmation required to update policy. Set 'confirm' to true."}

    if not policy_id: return {"success": False, "error": "policy_id is required"}
    if not update_data: return {"success": False, "error": "update_data cannot be empty"}

    is_valid, error_msg, validated_data = UniFiValidatorRegistry.validate("firewall_policy_update", update_data)
    if not is_valid:
        logger.warning(f"Invalid firewall policy update data for ID {policy_id}: {error_msg}")
        return {"success": False, "error": f"Invalid update data: {error_msg}"}

    if not validated_data:
         logger.warning(f"Firewall policy update data for ID {policy_id} is empty after validation.")
         return {"success": False, "error": "Update data is effectively empty or invalid."}

    updated_fields_list = list(validated_data.keys())
    logger.info(f"Attempting to update firewall policy '{policy_id}' with fields: {', '.join(updated_fields_list)}")
    try:
        success = await firewall_manager.update_firewall_policy(policy_id, validated_data)

        if success:
            updated_policy_obj = next((p for p in await firewall_manager.get_firewall_policies(include_predefined=True) if p.id == policy_id), None)
            updated_details = updated_policy_obj.raw if updated_policy_obj else {}
            logger.info(f"Successfully updated firewall policy ({policy_id})")
            return {
                "success": True, 
                "policy_id": policy_id,
                "updated_fields": updated_fields_list,
                "details": json.loads(json.dumps(updated_details, default=str))
                }
        else:
            logger.error(f"Failed to update firewall policy ({policy_id}). Manager returned false.")
            policy_after_update_obj = next((p for p in await firewall_manager.get_firewall_policies(include_predefined=True) if p.id == policy_id), None)
            details_after_attempt = policy_after_update_obj.raw if policy_after_update_obj else {}
            return {
                "success": False, 
                "policy_id": policy_id,
                "error": f"Failed to update firewall policy ({policy_id}). Check server logs.",
                "details_after_attempt": json.loads(json.dumps(details_after_attempt, default=str))
                }

    except Exception as e:
        logger.error(f"Error updating firewall policy {policy_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

# Simplified firewall creation is also BROKEN - not registered as tool
async def create_simple_firewall_policy(
    policy: Dict[str, Any],
    confirm: bool = False
) -> Dict[str, Any]:
    """⚠️ THIS FUNCTION IS BROKEN DUE TO UniFi API LIMITATIONS!
    
    The UniFi V2 Firewall API is incompletely implemented and firewall rule 
    creation does NOT work reliably. This is a known limitation of the UniFi 
    Controller and aiounifi library.
    
    PLEASE USE THESE ALTERNATIVES INSTEAD:
    1. **Network Isolation**: Go to Network settings → Select VLAN → Enable "Network Isolation"
    2. **Traffic Routes**: Use unifi_create_traffic_route for traffic management (works!)
    3. **Port Isolation**: Configure at switch port level with unifi_toggle_switch_port
    4. **Manual Setup**: Create firewall rules through UniFi Web UI
    
    Original (non-functional) description:
    Create a firewall rule with a compact schema and optional preview.

    High-level schema (validated internally):
    {
        "name":    "Block Xbox",
        "ruleset": "LAN_OUT",
        "action":  "drop",
        "src": {"type": "client_mac", "value": "4c:3b:df:2c:c8:c6"},
        "dst": {"type": "zone", "value": "wan"},
        "protocol": "all",           # optional
        "index": 2010,                # optional – will auto-place if omitted
        "enabled": true,              # default true
        "log": true                   # default false
    }

    If *confirm* is False (default) the function only validates and returns the
    fully-expanded UniFi payload in a preview. Set *confirm* to True to commit
    the rule and return the controller's response.
    """

    # IMMEDIATELY RETURN WITH ERROR AND ALTERNATIVES
    return {
        "success": False,
        "error": "Firewall rule creation is BROKEN due to UniFi V2 API bugs",
        "alternatives": [
            "1. Enable 'Network Isolation' in your VLAN settings (Settings → Networks → [Your VLAN] → Network Isolation)",
            "2. Use Traffic Routes instead: unifi_create_traffic_route (these work!)",
            "3. Configure port isolation at switch level: unifi_toggle_switch_port",
            "4. Create firewall rules manually in UniFi Web UI"
        ],
        "reason": "UniFi Controller V2 API does not properly accept firewall creation requests. This is a known limitation."
    }

@server.tool(
    name="unifi_list_firewall_zones",
    description="List controller firewall zones (V2 API)."
)
async def list_firewall_zones() -> Dict[str, Any]:
    zones = await firewall_manager.get_firewall_zones()
    return {"success": True, "count": len(zones), "zones": zones}

@server.tool(
    name="unifi_list_ip_groups",
    description="List IP groups configured on the controller (V2 API)."
)
async def list_ip_groups() -> Dict[str, Any]:
    groups = await firewall_manager.get_ip_groups()
    return {"success": True, "count": len(groups), "ip_groups": groups}
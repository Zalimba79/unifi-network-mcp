# Claude AI Instructions for UniFi Network MCP Server

## Important API Limitations

### ❌ Firewall Rule Creation is BROKEN

**DO NOT attempt to create firewall rules using:**
- `unifi_create_firewall_policy`
- `unifi_create_simple_firewall_policy`

These functions will ALWAYS fail due to UniFi V2 API bugs. This is NOT fixable in our code.

### ✅ Working Alternatives for Network Isolation

When users ask to block traffic between VLANs or create firewall rules, IMMEDIATELY suggest these working alternatives:

1. **Network Isolation** (BEST OPTION)
   - Tool: `unifi_update_network`
   - Set: `"networkgroup": "LAN"` and `"igmp_snooping": true`, `"dhcpguard_enabled": true`
   - Tell user: "Enable Network Isolation in the VLAN settings through the UniFi Web UI"

2. **Traffic Routes** (WORKS WELL)
   - Tool: `unifi_create_traffic_route`
   - Can route specific traffic to different interfaces
   - Fully functional alternative to firewall rules

3. **Switch Port Isolation**
   - Tool: `unifi_toggle_switch_port`
   - Can disable specific ports
   - Good for device-level isolation

4. **Manual Configuration**
   - Direct user to: UniFi Web UI → Settings → Firewall & Security
   - Explain that the API limitation requires manual setup

## Example Responses

### Bad Response ❌
"Let me create a firewall rule to block Kids VLAN from accessing other networks..."
*[Attempts unifi_create_firewall_policy which fails]*

### Good Response ✅
"I cannot create firewall rules directly due to UniFi API limitations, but I can help you achieve the same result using Network Isolation. Let me:
1. Show you how to enable Network Isolation for the Kids VLAN
2. OR set up Traffic Routes to control traffic flow
Which approach would you prefer?"

## Other Important Notes

### WAN Port Protection
- Port 9 is protected from being disabled
- This is hardcoded for safety
- Dream Machine Pro integrated controllers don't appear as devices

### DHCP/Fixed IP
- Use `unifi_set_client_fixed_ip` for reservations
- Works reliably

### Testing Commands
Before making changes, always:
1. List current configuration
2. Preview changes (if available)
3. Confirm with user
4. Apply with `confirm=true`

## Common User Requests and Correct Approaches

| User Wants | Don't Use | Use Instead |
|------------|-----------|-------------|
| Block VLAN to VLAN | ❌ Firewall rules | ✅ Network Isolation |
| Block specific device | ❌ Firewall rules | ✅ unifi_block_client |
| Control internet access | ❌ Firewall rules | ✅ Traffic Routes |
| Isolate IoT devices | ❌ Firewall rules | ✅ Network Isolation + separate VLAN |
| Port security | ❌ Firewall rules | ✅ Port Forwards with restrictions |

## Version Info
- Current Version: 0.4.2
- UniFi Controller Support: 5.x - 8.x
- Dream Machine Support: Yes (with limitations)
- Cloud API Support: No (local only)
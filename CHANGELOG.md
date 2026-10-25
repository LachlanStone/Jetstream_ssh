# Changelog

## 1.1.0

- Add `jetstream_vlans` module for creating VLANs with optional names and static or DHCP SVIs.
- Add prompt-based CLI mode detection so modules verify they are in global, VLAN, or interface config mode before sending commands.
- Fix `send_command` resending commands that legitimately return no output, which caused duplicate commands and `Error: Bad command` on the switch.
- Add opt-in timeout retries, including mode-aware retries that resend a config command only when the prompt has not changed.
- Fix `jetstream_acls` binding to use `access-list bind <id> interface vlan <vid>` and re-bind after `state: update`.
- Add unit tests for the VLAN module, VLAN command builder, config mode detection, and command helper.
- Add live tests for VLANs and expand the ACL live test to verify real switch state.

## 1.0.1

- Add `jetstream_user`, `jetstream_save` and `jetstream_command` modules.
- Add `meta/runtime.yml` and tighten `build_ignore` so the Galaxy tarball contains `plugins/`.

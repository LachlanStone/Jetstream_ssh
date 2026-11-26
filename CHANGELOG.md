# Changelog

## 1.2.0

- Add `jetstream_interfaces_v2` module: idempotent interface configuration supporting speed, state, description, PVID, tagged/untagged/disabled VLANs, and acceptable frame type.
- Add `interface_classes.py`: `InterfaceConfig` dataclass and supporting models for representing interface state.
- Add `interface_parsers.py`: parsers for `show interface configuration` and `show running-config` output to build current interface state.
- Fix `interface_builder.py`: emit negate command for `acceptable_frame_type all` and default omitted PVID to 1.
- Fix `send_command.py`: minor reliability improvements.
- Add unit tests for interface classes, parsers, v2 module, running config, and config mode (140 tests total).
- Add live test scripts for interface config and v2 module.

## 1.1.0 (unreleased — changes shipped as part of 1.2.0)

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

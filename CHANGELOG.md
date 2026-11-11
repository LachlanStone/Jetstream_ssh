# Changelog

## 1.1.0

- `jetstream_interfaces`: an omitted `description` is now left unchanged, while `description: ""` clears it. A `speed` of `null` sends `no speed`, and an omitted `pvid` sends `no switchport pvid`.
- `jetstream_interfaces`: change the defaults to `port_type: two-gigabitEthernet` and `speed: auto`.
- Fix `jetstream_acls` sending `logging enable` when the rule asked for `logging: disable`.
- Reject a rule that sets both `protocol` and `protocol_name` instead of emitting two `protocol` tokens.
- Exclude `.envrc` and `tests/` from the Galaxy artifact, and remove literal test passwords from the test fixtures.
- Move the example playbook to `extras/jetstream_switch_example.yml`, where the role README already points.
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

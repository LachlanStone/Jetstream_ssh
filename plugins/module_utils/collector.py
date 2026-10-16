class ResultCollector:
    """
    Collects results from every operation step.
    Only the main() function calls module.exit_json() or module.fail_json().
    Helpers NEVER call those methods — they append to this collector and return.
    """

    def __init__(self):
        self.switch = None
        self.verbosity = 0
        self.check_mode=False
        self.changed = False
        self.msg = ""
        self.stdout = ""           # Feature 1: Raw stdout from all commands
        self.stdout_lines = []     # Feature 1: Lines split for Ansible display
        self.parsed = {}           # Feature 2: Parsed output per command
        self.state = {}            # Feature 3: Generic before/after state tracking
        self._state_meta = {}      # Metadata for derived booleans per state key
        self.diff = {}             # Feature 4: Diff mode before/after
        self.last_command = ""        # The last command sent
        self.commands_sent = []    # Every command that was sent
        self.warnings = []
        self.verbosity = 0         # Ansible module verbosity level

        self.system_info = {}         # System information collected from the switch
        self.dns_info = {}            # DNS information collected from the switch

        # Internal tracking
        self._steps = []           # Per-step results for debugging
        self._current_step = 0

        # ACL Tracking
        self.acl_id = None  # The ACL ID being managed
        self.acl_state = {
            'starting': None,
            'finished': None
        }
        self.acl_bind_state = {
            'starting': None,
            'finished': None
        }

    def set_basic_info(self, switch=None, check_mode=False, verbosity=0):
        """Set basic information about the switch and check mode."""
        self.switch = switch
        self.check_mode = check_mode
        self.verbosity = verbosity

    def verbose(self, module, message, level=1):
        """Log a message when Ansible verbosity is at least ``level``."""
        if module is None:
            return
        if self.verbosity < level:
            self.set_verbosity(module)
        if self.verbosity >= level:
            module.log(str(message))

    def set_acl_info(self, acl_id: str = None, starting_bind: bool = None, finished_bind: bool = None, starting_acls: bool = None, finished_acls: bool = None):
        """Set the ACL ID in the collector."""
        if acl_id is not None:
            self.acl_id = str(acl_id)
        if self.acl_bind_state['starting'] is None and starting_bind is not None:
            self.acl_bind_state['starting'] = starting_bind
        if self.acl_bind_state['finished'] is None and finished_bind is not None:
            self.acl_bind_state['finished'] = finished_bind
        if self.acl_state['starting'] is None and starting_acls is not None:
            self.acl_state['starting'] = starting_acls
        if self.acl_state['finished'] is None and finished_acls is not None:
            self.acl_state['finished'] = finished_acls




    def add_step(self, name, step_result):
        """Add a normalized step result to the collector."""
        self._current_step += 1
        step_num = self._current_step

        if not isinstance(step_result, dict):
            step_result = {"value": step_result}

        normalized = {
            "step": step_num,
            "name": name,
            "changed": bool(step_result.get("changed", False)),
            "msg": step_result.get("msg", ""),
            "command": step_result.get("command", ""),
        }
        for key in ("commands", "stdout", "settings"):
            if key in step_result:
                normalized[key] = step_result[key]
        self.msg = step_result.get("msg", self.msg)
        self.name = name
        if step_result.get("changed", False):
            self.changed = True

#component: jetstream_acls.py | utilized to store ACL information in the ResultCollector
        if self.acl_id is not None:
            normalized["acl_info"] = {
                "id": self.acl_id,
                "is_bound": step_result.get("acl_bound", None),
                "was_bound": step_result.get("acl_was_bound", None),
                "is_present": step_result.get("acl_present", None),
                "was_present": step_result.get("acl_was_present", None),
            }
            self.acl_bind_state['finished'] = step_result.get("acl_bound", None)
            self.acl_state['finished'] = step_result.get("acl_present", None)

#component: jetstream_system | Store system_info from the step into self.system_info before building normalized
        incoming_system_info = step_result.get("system_info")
        if incoming_system_info and isinstance(incoming_system_info, dict):
            self.system_info.update(incoming_system_info)

        if self.system_info:
            normalized["system_info"] = dict(self.system_info)

        incoming_dns_info = step_result.get("dns_info")
        if incoming_dns_info and isinstance(incoming_dns_info, dict):
            self.dns_info.update(incoming_dns_info)

        if self.dns_info:
            normalized["dns_info"] = dict(self.dns_info)




        # Store the normalized step so it can be inspected later via result['steps'].
        # Keep the full per-step payload so each step can be reviewed independently.
        self._steps.append(normalized)

        command = step_result.get("command")
        if command is not None:
            self.last_command = command
            self.commands_sent.append(command)

        # Handle batch of commands sent in one step
        commands_sent_list = step_result.get("commands_sent")
        if commands_sent_list and isinstance(commands_sent_list, list):
            for cmd in commands_sent_list:
                self.commands_sent.append(cmd)
            self.last_command = commands_sent_list[-1]



    def return_info(self):
        result = {
            "msg": self.msg,
            "switch": self.switch,
            "current_state": self.name,
            "changed": self.changed,
            "check_mode": self.check_mode,
            "cmd": self.last_command,
        }
        if self.acl_id is not None and self.verbosity >= 2:
            result["acl_info"] = {
                "acl_id": self.acl_id,
                "bound_state": self.acl_bind_state,
                "state": self.acl_state,
            }

        if self.system_info is not None and self.verbosity >= 2:
            result["system_info"] = self.system_info

        if self.verbosity >= 3:
            result["steps"] = self._steps
        else:
            result["steps"] = [
                {key: value for key, value in step.items() if key in ("step", "name", "changed", "msg", "settings")}
                for step in self._steps
            ]
        if self.commands_sent is not None and self.verbosity >= 4:
            result["commands_sent"] = self.commands_sent

        return result

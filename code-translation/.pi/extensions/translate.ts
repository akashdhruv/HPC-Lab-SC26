// code-translation's pi commands; each runs one shell line you can also type yourself.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerShellCommands } from "../../../.pi/extensions/hpc-lab/shell";

export default function (pi: ExtensionAPI) {
	registerShellCommands(pi, {
		readiness: { description: "Which Fortran units can be translated now", run: "dev/bin/readiness" },
		check: { description: "Run the oracle in the container", run: "dev/bin/oracle" },
		approve: { description: 'Approve: /approve <name> plan | "Group 1" ["note"]', run: '../tools/approve dev/transformations/"$@"' },
		loop: { description: "Run the CodeScribe loop in the background: /loop <name> [loops]", run: 'dev/bin/loop -b "$@"' },
		status: { description: "Approvals, groups, log, loop runs: /status [name]", run: 'dev/bin/status "$@"' },
	});
}

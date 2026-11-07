// code-translation's pi commands; each runs one shell line you can also type yourself.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerShellCommands } from "../../../.pi/extensions/sc26/shell";

export default function (pi: ExtensionAPI) {
	registerShellCommands(pi, {
		readiness: { description: "Which Fortran units can be translated now", run: "dev/bin/readiness" },
		check: { description: "Run the oracle in the container", run: "dev/bin/oracle" },
		approve: { description: 'Approve: /approve <name> plan | "Group 1" ["note"]', run: '../tools/approve.sh dev/transformations/"$@"' },
		loop: { description: "Run the pi loop in the background: /loop <name> [loops]", run: 'dev/tools/pi-loop.sh -b "$@"' },
		codescribe: { description: "Run the CodeScribe loop instead: /codescribe <name> [-nloop 4]", run: 'dev/tools/codescribe-loop.sh -b "$@"' },
		status: { description: "Approvals, groups, log, loop output: /status [name]", run: 'dev/tools/status.sh "$@"' },
	});
}

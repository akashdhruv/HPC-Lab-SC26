// mxp-optimization's pi commands; each runs one shell line you can also type yourself.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerShellCommands } from "../../../.pi/extensions/sc26/shell";

export default function (pi: ExtensionAPI) {
	registerShellCommands(pi, {
		check: { description: "Build and test the app in the container", run: "dev/bin/box make check" },
		runs: { description: "List the stage runs (R)", run: "ls -d experiments/*/*-* 2>/dev/null || echo 'no runs yet'" },
		approve: { description: 'Approve: /approve <R> plan | result | "candidate <id>"', run: '../tools/approve.sh "$@"' },
		evolve: { description: "Start a search in a detached container: /evolve <R>", run: '../tools/approved.sh "$@" plan && dev/bin/box -d dev/tools/search.sh "$@"' },
		"evolve-status": { description: "Progress of a search: /evolve-status <R>", run: 'dev/bin/box make status EXP="$@"' },
		"evolve-stop": { description: "Stop the search container (make resume continues)", run: "docker stop sc26-mxp-optimization" },
	});
}

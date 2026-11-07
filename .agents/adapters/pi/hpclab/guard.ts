// Approvals are the scientist's: block the agent's own tool calls that would write approvals.toml
// or run tools/approve. The scientist's /approve runs outside the agent's tools, so it still works.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { basename } from "node:path";

const APPROVE = /(^|[\s\/'"])approve(\.cmd)?(\s|$)/;
const WRITES = /approvals\.toml/;

export function guardApprovals(pi: ExtensionAPI) {
	pi.on("tool_call", async (e: any) => {
		if ((e.toolName === "write" || e.toolName === "edit") && basename(String(e.input.path)) === "approvals.toml")
			return { block: true, reason: "approvals.toml is written only by the scientist (tools/approve)" };
		if (e.toolName === "bash" && (APPROVE.test(e.input.command) || (WRITES.test(e.input.command) && /[>]|tee|sed\s+-i|\bcp\b|\bmv\b|\brm\b/.test(e.input.command))))
			return { block: true, reason: "approvals are recorded only by the scientist: ask them to run tools/approve" };
	});
}

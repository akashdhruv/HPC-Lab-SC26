// During pi-loop phases (SC26_TASK set), enforce the task's loop.toml like CodeScribe does:
// bash allowlist, no shell operators, protected files, and a read-only reviewer.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { relative, resolve } from "node:path";

const DEFAULTS = ["ls", "pwd", "find", "grep", "head", "tail", "wc", "git", "test", "echo", "sed"];
const REVIEWER = ["ls", "pwd", "find", "grep", "head", "tail", "wc", "cat", "git", "diff", "readiness"];

export default function (pi: ExtensionAPI) {
	const task = process.env.SC26_TASK;
	if (!task) return;
	const toml = readFileSync(task, "utf8");
	const list = (key: string) =>
		[...(toml.match(new RegExp(`^${key}\\s*=\\s*\\[([\\s\\S]*?)\\]`, "m"))?.[1] ?? "").matchAll(/"([^"]+)"/g)].map((m) => m[1]);
	const reviewer = process.env.SC26_ROLE === "review";
	const allow = reviewer ? REVIEWER : [...DEFAULTS, ...list("bash")];
	const globs = [task, ...list("protect")].map((g) => new RegExp(`^${g.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, "[^/]*")}$`));
	const isProtected = (p: string) => globs.some((g) => g.test(relative(process.cwd(), resolve(p))));

	pi.on("tool_call", async (e: any) => {
		if (e.toolName === "write" || e.toolName === "edit") {
			if (reviewer) return { block: true, reason: "the reviewer is read-only" };
			if (isProtected(e.input.path)) return { block: true, reason: `${e.input.path} is protected by ${task}` };
		}
		if (e.toolName === "bash") {
			const words: string[] = e.input.command.trim().split(/\s+/);
			if (/[|&;><`$]/.test(e.input.command)) return { block: true, reason: "one plain command per call: no | & ; > < ` $" };
			if (!allow.includes(words[0])) return { block: true, reason: `'${words[0]}' is not allowed; allowed: ${allow.join(" ")}` };
			if (!reviewer && words.slice(1).some(isProtected)) return { block: true, reason: "a protected file is in the arguments" };
		}
	});
}

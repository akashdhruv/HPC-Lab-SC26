// The tutorial's .venv first on PATH for the agent's commands (tools make and activate it themselves);
// before it, with orchestrator.dev_bin_on_path in config.yaml, the stubs of every level from the
// session's folder up to the root, deepest first: each system's dev/bin, then the root's tools/.
import { existsSync } from "node:fs";
import { delimiter, dirname, join, relative } from "node:path";

export class Venv {
	readonly path: string;
	readonly root: string;

	constructor(config: string) { this.root = dirname(config); this.path = join(this.root, ".venv"); }

	get bin(): string { return join(this.path, process.platform === "win32" ? "Scripts" : "bin"); }

	bins(start: string): string[] {
		if (relative(this.root, start).startsWith("..")) return [];
		const out: string[] = [];
		for (let dir = start; ; dir = dirname(dir)) {
			if (dir === this.root) return [...out, join(dir, "tools")];
			if (existsSync(join(dir, "dev", "tools.py"))) out.push(join(dir, "dev", "bin"));
			if (dirname(dir) === dir) return out;
		}
	}

	engage(start: string, devBin: boolean) {
		const key = Object.keys(process.env).find((k) => k.toLowerCase() === "path") ?? "PATH";
		process.env.VIRTUAL_ENV = this.path;
		const front = [...(devBin ? this.bins(start) : []), this.bin];
		process.env[key] = [...front, process.env[key]].filter(Boolean).join(delimiter);
	}
}

// The tutorial's .venv, first on PATH for the agent's commands (entry points make and activate it themselves).
import { delimiter, dirname, join } from "node:path";

export class Venv {
	readonly path: string;

	constructor(config: string) { this.path = join(dirname(config), ".venv"); }

	get bin(): string { return join(this.path, process.platform === "win32" ? "Scripts" : "bin"); }

	engage() {
		const key = Object.keys(process.env).find((k) => k.toLowerCase() === "path") ?? "PATH";
		process.env.VIRTUAL_ENV = this.path;
		process.env[key] = [this.bin, process.env[key]].filter(Boolean).join(delimiter);
	}
}

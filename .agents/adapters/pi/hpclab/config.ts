// Reads the tutorial's config.yaml and turns it into the "hpclab/agent" pi provider.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

export const PROVIDER = "hpclab";
export const MODEL = "agent";

export class Config {
	readonly path: string;
	readonly data: Record<string, any> = {};
	readonly problem?: string;

	constructor(start: string) {
		this.path = Config.find(start);
		if (!existsSync(this.path)) { this.problem = `config.yaml not found above ${start}`; return; }
		this.data = Config.parse(readFileSync(this.path, "utf8"));
		if (!this.baseUrl || !this.apiKey) this.problem = `set OPENAI_COMP_BASEURL and OPENAI_COMP_APIKEY in ${this.path}`;
		else if (!this.model) this.problem = `set agent.model in ${this.path}`;
	}

	get baseUrl(): string { return this.data.OPENAI_COMP_BASEURL ?? ""; }
	get apiKey(): string { return this.data.OPENAI_COMP_APIKEY ?? ""; }
	get agent(): Record<string, any> { return this.data.agent ?? {}; }
	get model(): string { return this.agent.model ?? ""; }
	get devBinOnPath(): boolean { return this.data.orchestrator?.dev_bin_on_path === true; }
	get host(): string { try { return new URL(this.baseUrl).host; } catch { return this.baseUrl; } }

	provider() {
		const a = this.agent;
		return {
			baseUrl: this.baseUrl,
			apiKey: this.apiKey,
			api: "openai-completions" as const,
			compat: {
				supportsDeveloperRole: a.supports_developer_role ?? false,
				supportsReasoningEffort: a.supports_reasoning_effort ?? false,
			},
			models: [{
				id: MODEL,
				name: this.model,
				samplingParams: { model: this.model },
				reasoning: a.reasoning ?? false,
				input: ["text"] as ("text" | "image")[],
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
				contextWindow: a.context_window ?? 128000,
				maxTokens: a.max_tokens ?? 16384,
			}],
		};
	}

	async probe(): Promise<string> {
		const res = await fetch(`${this.baseUrl.replace(/\/$/, "")}/models`, { headers: { Authorization: `Bearer ${this.apiKey}` } });
		if (!res.ok) return `GET /models -> HTTP ${res.status}`;
		const ids = ((await res.json()).data ?? []).flatMap((m: any) => [m.id, m.internal_id]);
		return `${this.model} ${ids.includes(this.model) ? "available" : "NOT listed"}`;
	}

	static find(start: string): string {
		for (let dir = start; ; dir = dirname(dir)) {
			if (existsSync(join(dir, "config.yaml"))) return join(dir, "config.yaml");
			if (dirname(dir) === dir) return join(start, "config.yaml");
		}
	}

	static parse(text: string): Record<string, any> {
		const root: Record<string, any> = {};
		const stack: { indent: number; map: Record<string, any> }[] = [{ indent: -1, map: root }];
		for (const raw of text.split("\n")) {
			const m = raw.replace(/(^|\s+)#.*$/, "").match(/^(\s*)([\w.-]+):\s*(.*)$/);
			if (!m) continue;
			while (stack[stack.length - 1].indent >= m[1].length) stack.pop();
			const parent = stack[stack.length - 1].map;
			if (m[3] === "") stack.push({ indent: m[1].length, map: (parent[m[2]] = {}) });
			else parent[m[2]] = Config.scalar(m[3]);
		}
		return root;
	}

	static scalar(s: string): any {
		s = s.trim();
		if (s.startsWith("[")) return s.slice(1, -1).split(",").map((x) => String(Config.scalar(x))).filter(Boolean);
		if (/^(['"]).*\1$/.test(s)) s = s.slice(1, -1);
		else if (s === "true" || s === "false") return s === "true";
		else if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s);
		return s.replace(/\$\{(\w+)\}/g, (_, v) => process.env[v] ?? "");
	}
}

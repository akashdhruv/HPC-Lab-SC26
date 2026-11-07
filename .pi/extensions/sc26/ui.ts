// Re-registers pi's read/bash/edit/write tools with one-line output (ctrl+o expands).
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createBashTool, createEditTool, createReadTool, createWriteTool } from "@earendil-works/pi-coding-agent";
import { Text } from "@earendil-works/pi-tui";

const text = (r: any): string => (r.content?.[0]?.type === "text" ? r.content[0].text : "");
const lines = (s: string) => s.split("\n").filter((l) => l.trim()).length;

export class CompactTools {
	constructor(private pi: ExtensionAPI, private cwd: string) {}

	register() {
		this.wrap(createReadTool(this.cwd), (a) => a.path, (r) => `${lines(text(r))} lines`);
		this.wrap(createBashTool(this.cwd), (a) => a.command.split("\n")[0].slice(0, 90), (r) => `${lines(text(r))} lines`);
		this.wrap(createEditTool(this.cwd), (a) => a.path, (r) => {
			const diff: string = r.details?.diff ?? "";
			return `+${diff.split("\n").filter((l) => /^\+(?!\+\+)/.test(l)).length} / -${diff.split("\n").filter((l) => /^-(?!--)/.test(l)).length}`;
		});
		this.wrap(createWriteTool(this.cwd), (a) => `${a.path} (${a.content.split("\n").length} lines)`, () => "written");
	}

	private wrap(tool: any, call: (args: any) => string, summary: (r: any) => string) {
		this.pi.registerTool({
			...tool,
			async execute(...args: any[]) { return tool.execute(...args); },
			renderCall: (args: any, theme: any) => new Text(theme.fg("toolTitle", theme.bold(`${tool.name} `)) + theme.fg("accent", call(args)), 0, 0),
			renderResult: (r: any, { expanded, isPartial }: any, theme: any, ctx: any) => {
				if (isPartial) return new Text(theme.fg("warning", "…"), 0, 0);
				if (ctx?.isError) return new Text(theme.fg("error", `✗ ${text(r).split("\n")[0]}`), 0, 0);
				const body = expanded ? "\n" + theme.fg("dim", (r.details?.diff ?? text(r)).split("\n").slice(-12).join("\n")) : "";
				return new Text(theme.fg("success", summary(r)) + body, 0, 0);
			},
		});
	}
}

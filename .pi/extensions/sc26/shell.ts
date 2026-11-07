// Turns a table of shell lines into pi commands: /name args runs the line with pi's own bash
// (Git Bash on Windows) and prints the line and its output into the chat.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createBashTool } from "@earendil-works/pi-coding-agent";

export type ShellTable = Record<string, { description: string; run: string }>;

export function registerShellCommands(pi: ExtensionAPI, table: ShellTable) {
	const bash = createBashTool(process.cwd());

	for (const [name, { description, run }] of Object.entries(table)) {
		pi.registerCommand(name, {
			description: `${description}  ($ ${run})`,
			handler: async (args) => {
				const line = run.replace(/"\$@"/g, args.trim());
				let text: string;
				try {
					const result: any = await bash.execute(`sc26-${name}`, { command: line }, undefined as any, undefined as any);
					text = result.content?.[0]?.text ?? "";
				} catch (error) {
					text = String((error as Error).message ?? error);
				}
				const output = text.trimEnd().split("\n").slice(-40).join("\n");
				pi.sendMessage({ customType: "shell", display: true, content: `\`\`\`\n$ ${line}\n${output}\n\`\`\`` });
			},
		});
	}
}

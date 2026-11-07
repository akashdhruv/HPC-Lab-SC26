// Shared pi extension: sc26 provider from config.yaml, header, compact tool output, /sc26.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { basename } from "node:path";
import { Config, MODEL, PROVIDER } from "./config";
import { CompactTools } from "./ui";

export default function (pi: ExtensionAPI) {
	const root = process.cwd();
	const config = new Config(root);
	if (!config.problem) pi.registerProvider(PROVIDER, config.provider());
	new CompactTools(pi, root).register();

	pi.registerCommand("sc26", {
		description: "Test the endpoint in config.yaml",
		handler: async (_a, ctx) => ctx.ui.notify(config.problem ?? `${config.host}: ${await config.probe().catch(String)}`, config.problem ? "error" : "info"),
	});

	pi.on("session_start", async (_e, ctx) => {
		const t = ctx.ui.theme;
		const status = config.problem ? t.fg("error", `✗ ${config.problem}`) : t.fg("dim", `${config.model} @ ${config.host}`);
		ctx.ui.setWidget("sc26", [`${t.fg("accent", t.bold(`SC26 · ${basename(root)}`))}  ${status}  ${t.fg("dim", "· plan → approve → act → verify")}`]);
		ctx.ui.setToolsExpanded(false);
		// The startup model is chosen before this provider exists; switch without awaiting (awaiting deadlocks).
		const model = config.problem ? undefined : ctx.modelRegistry.find(PROVIDER, MODEL);
		if (model && ctx.model?.provider !== PROVIDER) void pi.setModel(model);
	});
}

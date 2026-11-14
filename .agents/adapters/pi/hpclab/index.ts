// Shared pi extension: hpclab provider from config.yaml, .venv (and dev/bin) on PATH, header, compact tool output, approvals guard, /hpclab.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { basename } from "node:path";
import { Config, MODEL, PROVIDER } from "./config";
import { CompactTools } from "./ui";
import { guardApprovals } from "./guard";
import { Venv } from "./venv";

export default function (pi: ExtensionAPI) {
	const root = process.cwd();
	const config = new Config(root);
	new Venv(config.path).engage(root);
	if (!config.problem) pi.registerProvider(PROVIDER, config.provider());
	new CompactTools(pi, root).register();
	guardApprovals(pi);

	pi.registerCommand("hpclab", {
		description: "Test the endpoint in config.yaml",
		handler: async (_a, ctx) => ctx.ui.notify(config.problem ?? `${config.host}: ${await config.probe().catch(String)}`, config.problem ? "error" : "info"),
	});

	pi.on("session_start", async (_e, ctx) => {
		const t = ctx.ui.theme;
		const status = config.problem ? t.fg("error", `✗ ${config.problem}`) : t.fg("dim", `${config.model} @ ${config.host}`);
		ctx.ui.setWidget("hpclab", [`${t.fg("accent", t.bold(`HPC Lab · ${basename(root)}`))}  ${status}  ${t.fg("dim", "· plan → approve → act → verify")}`]);
		ctx.ui.setToolsExpanded(false);
		// The startup model is chosen before this provider exists; switch without awaiting (awaiting deadlocks).
		const model = config.problem ? undefined : ctx.modelRegistry.find(PROVIDER, MODEL);
		if (model && ctx.model?.provider !== PROVIDER) void pi.setModel(model);
	});
}

import { DurableObject } from "cloudflare:workers";

const PORT = 8000;
const INACTIVITY_TIMEOUT_MS = 10 * 60 * 1000;

interface Env {
	FRIDAY_AGENT_CONTAINER: DurableObjectNamespace<FridayAgentContainer>;
	ANTHROPIC_API_KEY: string;
	ANTHROPIC_MODEL: string;
	RATE_LIMIT_PER_MINUTE: string;
	AGENT_MAX_ROUNDS: string;
	LITELLM_BASE_URL: string;
	LITELLM_API_KEY: string;
	LITELLM_MODEL: string;
	BRAVE_API_KEY: string;
}

export class FridayAgentContainer extends DurableObject<Env> {
	private starting: Promise<void> | undefined;
	private monitoring: Promise<void> | undefined;

	constructor(ctx: DurableObjectState, env: Env) {
		super(ctx, env);
		const container = ctx.container;
		if (container?.running) {
			// Restore the timeout and exit monitoring after a DO restart.
			void ctx.blockConcurrencyWhile(() =>
				container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS),
			);
			this.observeExit();
		}
	}

	async fetch(request: Request): Promise<Response> {
		// Share startup across concurrent requests, including after a failed attempt.
		this.starting ??= this.startAndWaitForPort().finally(() => {
			this.starting = undefined;
		});
		await this.starting;

		const url = new URL(request.url);
		url.protocol = "http:";
		url.host = "container";
		const forwarded = new Request(url, request);
		forwarded.headers.delete("host");
		return this.ctx.container!.getTcpPort(PORT).fetch(forwarded);
	}

	private async startAndWaitForPort(): Promise<void> {
		const container = this.ctx.container!;
		if (!container.running) {
			container.start({
				image: container.images.base,
				instance: "lite",
				enableInternet: true,
				env: {
					ANTHROPIC_API_KEY: this.env.ANTHROPIC_API_KEY,
					ANTHROPIC_MODEL: this.env.ANTHROPIC_MODEL,
					RATE_LIMIT_PER_MINUTE: this.env.RATE_LIMIT_PER_MINUTE,
					AGENT_MAX_ROUNDS: this.env.AGENT_MAX_ROUNDS,
					LITELLM_BASE_URL: this.env.LITELLM_BASE_URL,
					LITELLM_API_KEY: this.env.LITELLM_API_KEY,
					LITELLM_MODEL: this.env.LITELLM_MODEL,
					BRAVE_API_KEY: this.env.BRAVE_API_KEY,
				},
			});
		}
		this.observeExit();
		await container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS);

		// running means startup was requested, not that the HTTP server is ready.
		const port = container.getTcpPort(PORT);
		for (let attempt = 0; attempt < 100; attempt++) {
			try {
				const response = await port.fetch("http://container/health", {
					signal: AbortSignal.timeout(1000),
				});
				await response.body?.cancel();
				if (response.ok) return;
			} catch {
				// The port may not be listening yet. Retry the readiness probe only.
			}
			await scheduler.wait(200);
		}
		throw new Error("Container did not become ready on port 8000");
	}

	private observeExit(): void {
		if (this.monitoring) return;
		this.monitoring = this.ctx
			.container!.monitor()
			.then(() => console.log("Container exited successfully"))
			.catch((error: unknown) => console.error("Container failed:", error))
			.finally(() => {
				this.monitoring = undefined;
			});
		this.ctx.waitUntil(this.monitoring);
	}
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		return env.FRIDAY_AGENT_CONTAINER.getByName("singleton").fetch(request);
	},
};

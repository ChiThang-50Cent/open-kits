import { tool } from "@opencode-ai/plugin"

const PYTHON_BIN = process.env.DDGS_PYTHON_PATH || "python3"

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function currentDateISO() {
  return new Date().toISOString().slice(0, 10)
}

function injectToday(raw: string) {
  const today = currentDateISO()
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === "object") {
      return JSON.stringify({ today, ...parsed }, null, 2)
    }
  } catch {
    // Fall through and return raw output when it's not JSON.
  }
  return raw
}

function buildArgs(
  query: string,
  searchType: string,
  region: string,
  safesearch: string,
  backend: string,
  maxResults: number,
  page: number,
  timeout: number,
  snippetLength: number,
  timelimit?: string,
): string[] {
  const args = [
    "--query", query,
    "--search-type", searchType,
    "--region", region,
    "--safesearch", safesearch,
    "--backend", backend,
    "--max-results", String(maxResults),
    "--page", String(page),
    "--timeout", String(timeout),
    "--snippet-length", String(snippetLength),
  ]
  if (timelimit) {
    args.push("--timelimit", timelimit)
  }
  return args
}

export default tool({
  description: [
    "Search the web using a hybrid of DDGS and SearXNG.",
    "Responses include a top-level today field in YYYY-MM-DD format.",
    'Use search_type="text" for general web search, "news" for recent events and articles.',
    'For Vietnamese content prefer region="vn-vi"; for global results use region="us-en".',
    "Use timelimit to restrict results by recency: d=last day, w=last week, m=last month, y=last year.",
    "News results include date and publisher fields when available.",
    "This tool merges multi-source results while preserving the existing response schema.",
    "Use this tool whenever you need current information, URLs, or to verify facts.",
  ].join(" "),
  args: {
    query: tool.schema.string().min(1).describe("Search query"),
    search_type: tool.schema
      .enum(["text", "news"])
      .optional()
      .describe('Search type: "text" (default) or "news"'),
    region: tool.schema
      .string()
      .optional()
      .describe('Region code, e.g. "vn-vi" (default) or "us-en"'),
    safesearch: tool.schema
      .enum(["on", "moderate", "off"])
      .optional()
      .describe("Safe search mode (default: moderate)"),
    timelimit: tool.schema
      .enum(["d", "w", "m", "y"])
      .optional()
      .describe("Time window: d=day, w=week, m=month, y=year"),
    backend: tool.schema
      .string()
      .optional()
      .describe("DDGS backend hint (default: auto); hybrid execution still enabled"),
    max_results: tool.schema
      .number()
      .int()
      .min(1)
      .max(20)
      .optional()
      .describe("Number of results to return (default: 8, max: 20)"),
    page: tool.schema.number().int().min(1).optional().describe("Page number (default: 1)"),
    timeout: tool.schema
      .number()
      .int()
      .min(1)
      .max(30)
      .optional()
      .describe("Request timeout in seconds (default: 8)"),
    snippet_length: tool.schema
      .number()
      .int()
      .min(50)
      .max(2000)
      .optional()
      .describe("Max snippet length in characters (default: 500)"),
  },
  async execute(args) {
    const scriptPath = new URL("./ddgs-search.py", import.meta.url).pathname
    const maxResults = clamp(args.max_results ?? 8, 1, 20)
    const page = args.page ?? 1
    const timeout = clamp(args.timeout ?? 8, 1, 30)
    const snippetLength = clamp(args.snippet_length ?? 500, 50, 2000)

    const cmdArgs = buildArgs(
      args.query,
      args.search_type ?? "text",
      args.region ?? "vn-vi",
      args.safesearch ?? "moderate",
      args.backend ?? "auto",
      maxResults,
      page,
      timeout,
      snippetLength,
      args.timelimit,
    )

    try {
      const output = await Bun.$`${PYTHON_BIN} ${scriptPath} ${cmdArgs}`.text()
      return injectToday(output.trim())
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      return JSON.stringify(
        {
          today: currentDateISO(),
          ok: false,
          query: args.query,
          results: [],
          error: {
            code: "PYTHON_EXEC_ERROR",
            message,
            retryable: true,
          },
        },
        null,
        2,
      )
    }
  },
})

"""Local stdio MCP server used only by the live adapter integration test."""

from mcp.server.fastmcp import FastMCP


server = FastMCP("FAM MCP reference", json_response=True)


@server.resource("fam-test://document")
def document() -> str:
    return "resident neural fabric"


@server.tool()
def lookup(query: str) -> dict[str, str]:
    return {"result": query.upper()}


@server.tool()
def replace(text: str) -> dict[str, bool]:
    return {"changed": bool(text)}


if __name__ == "__main__":
    server.run(transport="stdio")

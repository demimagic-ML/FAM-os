import { createReadStream } from "node:fs";
import { createServer } from "node:http";
import { resolve } from "node:path";

const port = Number(process.argv[2] || 43119);
const file = resolve("dist/index.html");
const server = createServer((request, response) => {
  if (request.url !== "/" && request.url !== "/index.html") {
    response.writeHead(404).end("not found");
    return;
  }
  response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  createReadStream(file).pipe(response);
});
server.listen(port, "127.0.0.1", () => console.log(`ready:${port}`));

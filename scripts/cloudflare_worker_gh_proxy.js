/**
 * Cloudflare Worker: GitHub 加速反代（gh-proxy 前缀风格，自建专用）
 *
 * 用法（与 auto_download_qlib_bin.sh 的 MIRROR_PREFIXES 前缀格式一致）：
 *   https://<your-worker>.workers.dev/https://github.com/<owner>/<repo>/releases/download/...
 *
 * 部署（Dashboard 方式，无需本地 CLI）：
 *   1. dash.cloudflare.com → Workers & Pages → Create → Create Worker
 *   2. 命名后点 Deploy，再点 Edit code，粘贴本文件全部内容，Deploy
 *   3. 重要：*.workers.dev 在中国大陆被 DNS 污染/SNI 阻断（实测解析到假 IP），
 *      直连通常不可用。请在 Worker 的 Settings → Domains & Routes 绑定自有
 *      自定义域（Custom Domains），再把自定义域地址加入
 *      auto_download_qlib_bin.sh 的 MIRROR_PREFIXES 首位（自建最稳，公共镜像只作兜底）
 *
 * 依赖的行为（aria2c 多连接下载可用性）：
 *   - Range 头随请求透传，206 分段响应原样回传 → aria2c -x 16 -s 16 分段下载
 *   - GitHub release 链路的 302 跳转（github.com → release-assets.githubusercontent.com）
 *     改写回本 Worker 前缀下，整条链路保持加速
 *   - 域名白名单限制 GitHub 系主机，避免沦为开放代理
 */

const ALLOWED_HOST_SUFFIXES = [
  "github.com",
  "githubusercontent.com", // objects. / release-assets. / codeload. 等跳转目标
  "github.io",
];

export default {
  async fetch(request) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("method not allowed\n", { status: 405 });
    }

    const reqUrl = new URL(request.url);
    const target = reqUrl.pathname.slice(1) + reqUrl.search;

    // 优先按原文解析：decodeURIComponent 会把签名 URL 里的 %2F 改写成 /，
    // 破坏查询签名（SigV4/Azure SAS 类）；仅当原文不是合法 URL 时才尝试解码
    let targetUrl;
    try {
      targetUrl = new URL(target);
    } catch {
      try {
        targetUrl = new URL(decodeURIComponent(target));
      } catch {
        return new Response("usage: /https://github.com/<owner>/<repo>/...\n", { status: 400 });
      }
    }

    const host = targetUrl.hostname;
    const allowed = ALLOWED_HOST_SUFFIXES.some(
      (s) => host === s || host.endsWith("." + s),
    );
    if (!allowed) {
      return new Response("host not allowed\n", { status: 403 });
    }
    // 仅允许标准 https 与默认端口，杜绝协议/端口维度的滥用面
    if (targetUrl.protocol !== "https:" || targetUrl.port !== "") {
      return new Response("protocol/port not allowed\n", { status: 400 });
    }

    // new Request(targetUrl, request) 会复制包括 Range 在内的请求头
    let upstream;
    try {
      upstream = await fetch(new Request(targetUrl, request), {
        redirect: "manual",
      });
    } catch {
      return new Response("upstream fetch failed\n", { status: 502 });
    }

    if (upstream.status >= 300 && upstream.status < 400) {
      const location = upstream.headers.get("location");
      if (location) {
        // 相对/绝对 Location 统一转绝对路径后挂回本 Worker 前缀
        const abs = new URL(location, targetUrl).toString();
        return new Response(null, {
          status: upstream.status,
          headers: { location: "/" + abs },
        });
      }
    }

    const headers = new Headers(upstream.headers);
    headers.set("access-control-allow-origin", "*");
    // 声明了 content-encoding 就必须连带去掉 length：运行时可能已解码正文，
    // 头与字节流不一致会让客户端二次解码/按错误长度分段的
    if (headers.has("content-encoding")) {
      headers.delete("content-encoding");
      headers.delete("content-length");
    }
    return new Response(upstream.body, { status: upstream.status, headers });
  },
};

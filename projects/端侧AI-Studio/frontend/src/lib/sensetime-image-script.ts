/** 画布上商汤生图的调用脚本。地址指向本机后端，真钥匙不写在这里。 */

export const LOCAL_IMAGE_BASE_URL = "http://127.0.0.1:8000";
export const LOCAL_IMAGE_API_KEY = "local";
export const SENSENOVA_IMAGE_MODEL = "sensenova-u1.5-fast";
/** 旧版本存下来的模型名。读到时自动换成 Fast。 */
export const LEGACY_SENSENOVA_IMAGE_MODEL = "sensenova-u1.5-lite";
export const DEEPSEEK_TEXT_MODEL = "deepseek-flash";

export const DEEPSEEK_TEXT_SCRIPT = `async function generateText({ messages, baseUrl, apiKey, request, onDelta, params }) {
  const root = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const workflow = params && params.workflow === "drama" ? "drama" : "ecommerce";
  const task = params && params.task ? params.task : "summary";
  const data = await request({
    method: "post",
    url: root + "/v1/responses",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + apiKey },
    data: { input: messages, workflow: workflow, task: task, purpose: params && params.purpose ? params.purpose : "" },
  });
  const text = data.output_text || "";
  if (onDelta) onDelta(text);
  return text;
}

return await generateText({ messages, baseUrl, apiKey, request, onDelta, params });
`;

export const SENSENOVA_IMAGE_SCRIPT = `async function generateImage({ prompt, images, params, model, baseUrl, apiKey, request }) {
  const rawSize = params && params.size ? String(params.size) : "";
  const size = rawSize === "auto" || rawSize.indexOf("x") > 0 ? rawSize : "2048x2048";
  const watermark = params && (params.watermark === true || params.watermark === "true");
  const promptExtend = params && (params.promptExtend === true || params.promptExtend === "true");
  if (!images.length) {
    const data = await request({
      method: "post",
      url: (baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl) + "/v1/images/generations",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + apiKey },
      data: { model, prompt, n: 1, size, watermark, prompt_extend: promptExtend, response_format: "b64_json", output_format: "png" },
    });
    return (data.data || []).map((item) => item.b64_json ? "data:image/png;base64," + item.b64_json : item.url);
  }
  const form = new FormData();
  form.set("model", model);
  form.set("prompt", prompt);
  form.set("n", "1");
  form.set("size", size);
  form.set("watermark", watermark ? "true" : "false");
  form.set("prompt_extend", promptExtend ? "true" : "false");
  form.set("response_format", "b64_json");
  form.set("output_format", "png");
  const field = images.length > 1 ? "image[]" : "image";
  for (const dataUrl of images) {
    form.append(field, await (await fetch(dataUrl)).blob(), "ref.png");
  }
  const edited = await request({
    method: "post",
    url: (baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl) + "/v1/images/edits",
    headers: { Authorization: "Bearer " + apiKey },
    data: form,
  });
  return (edited.data || []).map((item) => item.b64_json ? "data:image/png;base64," + item.b64_json : item.url);
}

return await generateImage({ prompt, images, params, model, baseUrl, apiKey, request });
`;

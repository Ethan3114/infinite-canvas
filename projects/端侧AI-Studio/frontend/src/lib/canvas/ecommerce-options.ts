/** 电商生图选项。用途和比例都可多选；张数由勾选结果决定，不再裁切。 */

export type EcommercePurpose = {
    id: "main" | "scene" | "product";
    label: string;
    instruction: string;
};

export const ECOMMERCE_PURPOSES: EcommercePurpose[] = [
    { id: "main", label: "主图", instruction: "纯净背景，棚拍光，商品居中占画面主体，完整正面展示外观。" },
    { id: "scene", label: "场景图", instruction: "把商品放进真实生活场景，有环境和搭配道具，自然光，保留商品外观、颜色和包装。" },
    { id: "product", label: "商品图", instruction: "突出细节和卖点的特写或局部放大，换一个取景角度，不要写成整体正面居中的主图。" },
];

/** 商汤文档给出的建议尺寸。宽高都是 32 的倍数，且在 512 到 4096 之间。 */
export const SENSENOVA_SIZES = [
    { id: "auto", label: "自动", pixels: "auto", hint: "有参考图时跟着主图" },
    { id: "2048x2048", label: "1:1", pixels: "2048x2048", hint: "2K" },
    { id: "2720x1536", label: "16:9", pixels: "2720x1536", hint: "2K" },
    { id: "1536x2720", label: "9:16", pixels: "1536x2720", hint: "2K" },
    { id: "2496x1664", label: "3:2", pixels: "2496x1664", hint: "2K" },
    { id: "1664x2496", label: "2:3", pixels: "1664x2496", hint: "2K" },
    { id: "4096x4096", label: "1:1", pixels: "4096x4096", hint: "4K" },
] as const;

let activePurpose = "main";
let activeImageRequest = { watermark: false, promptExtend: false };

export function setActiveEcommercePurpose(purposeId: string) {
    activePurpose = purposeId;
}

export function getActiveEcommercePurpose() {
    return activePurpose;
}

export function setActiveImageRequest(value: { watermark: boolean; promptExtend: boolean }) {
    activeImageRequest = value;
}

export function getActiveImageRequest() {
    return activeImageRequest;
}

export function readEcommercePurposes(value: string | undefined): EcommercePurpose[] {
    const picked = new Set((value || "").split(",").map((item) => item.trim()).filter(Boolean));
    const purposes = ECOMMERCE_PURPOSES.filter((item) => picked.has(item.id));
    return purposes.length ? purposes : [ECOMMERCE_PURPOSES[0]];
}

export function readEcommerceSizes(value: string | undefined): string[] {
    const allowed = new Set(SENSENOVA_SIZES.map((item) => item.pixels));
    const sizes = (value || "").split(",").map((item) => item.trim()).filter((item) => allowed.has(item as (typeof SENSENOVA_SIZES)[number]["pixels"]));
    return sizes.length ? sizes : ["2048x2048"];
}

export function toggleCsv(current: string | undefined, id: string, fallback: string): string {
    const items = (current || fallback).split(",").map((item) => item.trim()).filter(Boolean);
    const next = items.includes(id) ? items.filter((item) => item !== id) : [...items, id];
    return (next.length ? next : [fallback.split(",")[0]]).join(",");
}

/** 出图不选目的。已经连上的提示词各算一条，写了什么就按什么出。 */
export function linkedImagePrompts(nodeId: string, nodes: { id: string; type: string; metadata?: { content?: string } }[], connections: { fromNodeId: string; toNodeId: string }[]): string[] {
    const prompts: string[] = [];
    for (const item of connections) {
        const otherId = item.toNodeId === nodeId ? item.fromNodeId : item.fromNodeId === nodeId ? item.toNodeId : "";
        if (!otherId) continue;
        const node = nodes.find((entry) => entry.id === otherId);
        if (node?.type !== "text") continue;
        const content = node.metadata?.content?.trim();
        if (content) prompts.push(content);
    }
    return prompts;
}

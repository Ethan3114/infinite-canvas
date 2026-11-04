import { CanvasNodeType, type CanvasConnection, type CanvasNodeData } from "@/types/canvas";

export type PlotShot = { no: number; text: string };

const SHOT_LIMIT = 3;

export function parsePlotShots(content: string): PlotShot[] {
    const shots: PlotShot[] = [];
    for (const line of content.split("\n")) {
        const matched = line.trim().match(/^镜头\s*(\d+)｜(.+)$/);
        if (!matched) continue;
        shots.push({ no: Number(matched[1]), text: matched[2].trim() });
        if (shots.length >= SHOT_LIMIT) break;
    }
    return shots;
}

/** 只摆出可点击的格子和连线，不调用生图。每张分镜图都接上同一组参考图。 */
export function buildShotFrameGraph(
    anchor: { x: number; y: number; width: number },
    plotNodeId: string,
    shots: PlotShot[],
    referenceIds: string[],
) {
    const nodes: CanvasNodeData[] = [];
    const connections: CanvasConnection[] = [];
    const imageModel = "default::sensenova-u1.5-lite";
    shots.forEach((shot, index) => {
        const y = anchor.y + index * 520;
        const textId = `shot-text-${plotNodeId}-${shot.no}`;
        const configId = `shot-config-${plotNodeId}-${shot.no}`;
        const imageId = `shot-image-${plotNodeId}-${shot.no}`;
        nodes.push({
            id: textId,
            type: CanvasNodeType.Text,
            title: `镜头 ${shot.no}`,
            position: { x: anchor.x + anchor.width + 80, y },
            width: 300,
            height: 160,
            metadata: { content: shot.text, prompt: shot.text, status: "success", fontSize: 14, plotSpawnOf: plotNodeId },
        });
        nodes.push({
            id: configId,
            type: CanvasNodeType.Config,
            title: `镜头 ${shot.no} 生图`,
            position: { x: anchor.x + anchor.width + 420, y },
            width: 360,
            height: 480,
            metadata: {
                status: "idle",
                generationMode: "image",
                dramaTask: "shotImage",
                outputNodeId: imageId,
                model: imageModel,
                composerContent: "只画这一镜。人物、场景、道具跟着连上的参考图。",
                prompt: "只画这一镜。人物、场景、道具跟着连上的参考图。",
                count: 1,
                size: "1024x1024",
                plotSpawnOf: plotNodeId,
            },
        });
        nodes.push({
            id: imageId,
            type: CanvasNodeType.Image,
            title: `镜头 ${shot.no} 画面 · 尚未生成`,
            position: { x: anchor.x + anchor.width + 840, y: y + 80 },
            width: 340,
            height: 240,
            metadata: { status: "idle", pendingResult: true, plotSpawnOf: plotNodeId },
        });
        connections.push(
            { id: `spawn-${plotNodeId}-text-${shot.no}`, fromNodeId: plotNodeId, toNodeId: textId },
            { id: `spawn-${plotNodeId}-shot-${shot.no}`, fromNodeId: textId, toNodeId: configId },
            { id: `spawn-${plotNodeId}-out-${shot.no}`, fromNodeId: configId, toNodeId: imageId },
        );
        referenceIds.forEach((referenceId, refIndex) => {
            connections.push({ id: `spawn-${plotNodeId}-ref-${shot.no}-${refIndex}`, fromNodeId: referenceId, toNodeId: configId });
        });
        if (index === 0) return;
        const previous = shots[index - 1];
        const videoConfigId = `shot-video-config-${plotNodeId}-${previous.no}-${shot.no}`;
        const videoId = `shot-video-${plotNodeId}-${previous.no}-${shot.no}`;
        const previousImageId = `shot-image-${plotNodeId}-${previous.no}`;
        nodes.push({
            id: videoConfigId,
            type: CanvasNodeType.Config,
            title: `镜头 ${previous.no}→${shot.no} 视频`,
            position: { x: anchor.x + anchor.width + 1240, y: y - 260 },
            width: 360,
            height: 480,
            metadata: {
                status: "idle",
                generationMode: "video",
                dramaTask: "clip",
                outputNodeId: videoId,
                seconds: "3",
                composerContent: "用前一镜当首帧，这一镜当尾帧。两条加起来覆盖这 9 秒里的一段。",
                prompt: "用前一镜当首帧，这一镜当尾帧。",
                plotSpawnOf: plotNodeId,
            },
        });
        nodes.push({
            id: videoId,
            type: CanvasNodeType.Video,
            title: `镜头 ${previous.no}→${shot.no} · 尚未生成`,
            position: { x: anchor.x + anchor.width + 1660, y: y - 180 },
            width: 420,
            height: 236,
            metadata: { status: "idle", pendingResult: true, plotSpawnOf: plotNodeId },
        });
        connections.push(
            { id: `spawn-${plotNodeId}-vf-${shot.no}`, fromNodeId: previousImageId, toNodeId: videoConfigId },
            { id: `spawn-${plotNodeId}-vl-${shot.no}`, fromNodeId: imageId, toNodeId: videoConfigId },
            { id: `spawn-${plotNodeId}-vout-${shot.no}`, fromNodeId: videoConfigId, toNodeId: videoId },
        );
    });
    const videoIds = nodes.filter((node) => node.type === CanvasNodeType.Video).map((node) => node.id);
    if (videoIds.length >= 2) {
        const joinId = `shot-join-${plotNodeId}`;
        const finalId = `shot-final-${plotNodeId}`;
        nodes.push({
            id: joinId,
            type: CanvasNodeType.Config,
            title: "拼接成片",
            position: { x: anchor.x + anchor.width + 1240, y: anchor.y + shots.length * 520 },
            width: 360,
            height: 480,
            metadata: {
                status: "idle",
                generationMode: "video",
                dramaTask: "join",
                outputNodeId: finalId,
                composerContent: "把各段视频按镜头顺序接成一条。不调用模型，不另扣费。",
                prompt: "把各段视频按镜头顺序接成一条。",
                plotSpawnOf: plotNodeId,
            },
        });
        nodes.push({
            id: finalId,
            type: CanvasNodeType.Video,
            title: "成片 · 尚未生成",
            position: { x: anchor.x + anchor.width + 1660, y: anchor.y + shots.length * 520 + 80 },
            width: 420,
            height: 236,
            metadata: { status: "idle", pendingResult: true, plotSpawnOf: plotNodeId },
        });
        videoIds.forEach((videoId, index) => {
            connections.push({ id: `spawn-${plotNodeId}-join-${index}`, fromNodeId: videoId, toNodeId: joinId });
        });
        connections.push({ id: `spawn-${plotNodeId}-final`, fromNodeId: joinId, toNodeId: finalId });
    }
    return { nodes, connections };
}

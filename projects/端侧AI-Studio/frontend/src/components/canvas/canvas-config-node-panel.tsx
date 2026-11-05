import type { CSSProperties } from "react";
import { Image as ImageIcon, LoaderCircle, MessageSquare, Music2, Play, Settings2, Square, Video } from "lucide-react";
import { Button, Segmented } from "antd";
import { useTranslation } from "react-i18next";

import { ModelPicker } from "@/components/model-picker";
import { defaultConfig, resolveModelForCapability, useConfigStore, useEffectiveConfig, type AiConfig } from "@/stores/use-config-store";
import { canvasThemes } from "@/lib/canvas-theme";
import { useThemeStore } from "@/stores/use-theme-store";
import { CanvasImageSettingsPopover } from "./canvas-image-settings-popover";
import { EcommerceOptionsPanel } from "./ecommerce-options-panel";
import { readEcommercePurposes, readEcommerceSizes } from "@/lib/canvas/ecommerce-options";
import { CanvasAudioSettingsPopover, type CanvasAudioSettingKey } from "./canvas-audio-settings-popover";
import { CanvasVideoSettingsPopover } from "./canvas-video-settings-popover";
import { CanvasTextSettingsPopover } from "./canvas-text-settings-popover";
import type { CanvasGenerationMode, CanvasNodeData, CanvasNodeMetadata } from "@/types/canvas";
import { getActiveWorkflow } from "@/lib/canvas/workflow";
import { DRAMA_TASKS, findDramaTask } from "@/lib/canvas/drama-tasks";

type CanvasConfigNodePanelProps = {
    node: CanvasNodeData;
    isRunning: boolean;
    inputSummary: { textCount: number; imageCount: number; videoCount: number; audioCount: number };
    linkedPromptCount?: number;
    onConfigChange: (nodeId: string, patch: Partial<CanvasNodeMetadata>) => void;
    onGenerate: (nodeId: string) => void;
    onStop: (nodeId: string) => void;
    onComposerToggle: () => void;
};

export function CanvasConfigNodePanel({ node, isRunning, inputSummary, linkedPromptCount = 0, onConfigChange, onGenerate, onStop, onComposerToggle }: CanvasConfigNodePanelProps) {
    const { t } = useTranslation();
    const globalConfig = useEffectiveConfig();
    const openConfigDialog = useConfigStore((state) => state.openConfigDialog);
    const theme = canvasThemes[useThemeStore((state) => state.theme)];
    const mode = node.metadata?.generationMode || "image";
    const drama = getActiveWorkflow() === "drama";
    const dramaTask = findDramaTask(node.metadata?.dramaTask);
    const config = buildNodeConfig(globalConfig, node, mode);
    const chipStyle = { background: theme.node.fill, borderColor: theme.node.stroke, color: theme.node.text };
    const hasAnyInput = Boolean(inputSummary.textCount || inputSummary.imageCount || inputSummary.videoCount || inputSummary.audioCount);
    const hasComposerContent = Boolean((node.metadata?.composerContent ?? node.metadata?.prompt ?? "").trim());
    const canGenerate = hasComposerContent || (mode === "audio" ? inputSummary.textCount > 0 : hasAnyInput);
    const ecommerce = !drama && (mode === "image" || mode === "text");
    const purposeCount = readEcommercePurposes(node.metadata?.ecommercePurposes).length;
    const sizeCount = readEcommerceSizes(node.metadata?.ecommerceSizes).length;
    const ecommerceCount = mode === "image" ? Math.max(1, linkedPromptCount) * sizeCount * Math.max(1, inputSummary.imageCount) : purposeCount;

    return (
        <div className="flex h-full w-full cursor-move flex-col overflow-hidden px-3 pb-3 pt-7 text-sm" style={{ color: theme.node.text }} onWheel={(event) => event.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between gap-3">
                <div className="shrink-0 text-sm font-semibold">{t("canvas.configNode.title")}</div>
                <div className="cursor-default" onMouseDown={(event) => event.stopPropagation()} onPointerDown={(event) => event.stopPropagation()}>
                    {drama ? (
                        <Segmented
                            size="small"
                            value={mode === "video" ? "video" : mode === "image" ? "image" : "text"}
                            onChange={(value) => {
                                const kind = value as "text" | "image" | "video";
                                const nextTasks = DRAMA_TASKS.filter((item) => item.kind === kind);
                                const next = nextTasks.some((item) => item.id === dramaTask.id) ? dramaTask : nextTasks[0];
                                onConfigChange(node.id, {
                                    generationMode: kind,
                                    dramaTask: next?.id,
                                    model: kind === "text" ? globalConfig.textModel : kind === "image" ? globalConfig.imageModel : node.metadata?.model,
                                    count: 1,
                                });
                            }}
                            options={[
                                { value: "text", label: t("canvas.configNode.text") },
                                { value: "image", label: t("canvas.configNode.image") },
                                { value: "video", label: t("canvas.configNode.video") },
                            ]}
                        />
                    ) : (
                        <Segmented
                        size="small"
                        className="canvas-config-mode !rounded-md !p-0.5"
                        value={mode}
                        onChange={(value) => onConfigChange(node.id, { generationMode: value as CanvasGenerationMode })}
                        options={[
                            {
                                value: "image",
                                label: (
                                    <span className="inline-flex items-center gap-1">
                                        <ImageIcon className="size-3.5" />
                                        {t("canvas.configNode.image")}
                                    </span>
                                ),
                            },
                            {
                                value: "text",
                                label: (
                                    <span className="inline-flex items-center gap-1">
                                        <MessageSquare className="size-3.5" />
                                        {t("canvas.configNode.text")}
                                    </span>
                                ),
                            },
                            {
                                value: "video",
                                label: (
                                    <span className="inline-flex items-center gap-1">
                                        <Video className="size-3.5" />
                                        {t("canvas.configNode.video")}
                                    </span>
                                ),
                            },
                            {
                                value: "audio",
                                label: (
                                    <span className="inline-flex items-center gap-1">
                                        <Music2 className="size-3.5" />
                                        {t("canvas.configNode.audio")}
                                    </span>
                                ),
                            },
                        ]}
                        />
                    )}
                </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
            {drama ? (
                <div className="mb-2 cursor-default" onMouseDown={(event) => event.stopPropagation()} onPointerDown={(event) => event.stopPropagation()} onWheel={(event) => event.stopPropagation()}>
                    <div className="flex max-h-72 flex-col gap-1 overflow-y-auto pr-1">
                        {DRAMA_TASKS.filter((item) => item.kind === (mode === "video" ? "video" : mode === "image" ? "image" : "text")).map((item) => {
                            const selected = item.id === dramaTask.id;
                            return (
                                <button
                                    key={item.id}
                                    type="button"
                                    className="rounded-lg px-2 py-1.5 text-left text-xs"
                                    style={{ background: selected ? theme.node.text : theme.node.fill, color: selected ? theme.node.panel : theme.node.text }}
                                    onMouseDown={(event) => event.stopPropagation()}
                                    onPointerDown={(event) => event.stopPropagation()}
                                    onClick={() =>
                                        onConfigChange(node.id, {
                                            dramaTask: item.id,
                                            generationMode: item.kind,
                                            model: item.kind === "text" ? globalConfig.textModel : globalConfig.imageModel,
                                            count: 1,
                                        })
                                    }
                                >
                                    {t(item.labelKey)}
                                </button>
                            );
                        })}
                    </div>
                    <p className="mt-1 text-[11px] leading-5" style={{ color: theme.node.muted }}>{t(dramaTask.hintKey)}</p>
                </div>
            ) : ecommerce ? (
                <EcommerceOptionsPanel
                    mode={mode === "text" ? "text" : "image"}
                    metadata={node.metadata}
                    textColor={theme.node.text}
                    mutedColor={theme.node.muted}
                    fill={theme.node.fill}
                    onChange={(patch) => onConfigChange(node.id, patch)}
                />
            ) : null}

            <div className="mb-2 flex flex-wrap gap-1.5">
                <InputChip label={t("canvas.configNode.prompt")} value={t("canvas.configNode.items", { count: inputSummary.textCount })} style={chipStyle} />
                <InputChip label={t("canvas.configNode.references")} value={t("canvas.configNode.images", { count: inputSummary.imageCount })} style={chipStyle} />
                <InputChip label={t("canvas.configNode.videoReferences")} value={t("canvas.configNode.items", { count: inputSummary.videoCount })} style={chipStyle} />
                <InputChip label={t("canvas.configNode.audioReferences")} value={t("canvas.configNode.items", { count: inputSummary.audioCount })} style={chipStyle} />
                <button type="button" className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-md border px-2 text-[11px]" style={chipStyle} onMouseDown={(event) => event.stopPropagation()} onClick={onComposerToggle}>
                    <Settings2 className="size-3.5" />
                    {t("canvas.configNode.compose")}
                </button>
            </div>

            <div className="mb-2 grid min-w-0 cursor-default grid-cols-[minmax(0,1fr)_148px] items-center gap-2" onMouseDown={(event) => event.stopPropagation()}>
                <ModelPicker className="canvas-compact-control h-10" config={config} value={config.model} onChange={(model) => onConfigChange(node.id, { model })} capability={mode} onMissingConfig={() => openConfigDialog(true)} fullWidth />
                {mode === "video" ? (
                    <CanvasVideoSettingsPopover config={config} placement="topRight" buttonClassName="canvas-compact-control !h-10 !w-full !justify-start !rounded-lg !px-2" onConfigChange={(key, value) => onConfigChange(node.id, videoConfigPatch(key, value))} />
                ) : mode === "image" && !ecommerce ? (
                    <CanvasImageSettingsPopover config={config} placement="topRight" autoAdjustOverflow={false} buttonClassName="canvas-compact-control !h-10 !w-full !justify-start !rounded-lg !px-2" onConfigChange={(key, value) => onConfigChange(node.id, key === "count" ? { count: Number(value) || 1 } : { [key]: value })} />
                ) : mode === "image" ? (
                    <div className="canvas-compact-control flex h-10 items-center truncate rounded-lg border px-2 text-xs" style={chipStyle}>{t("canvas.configNode.images", { count: ecommerceCount })}</div>
                ) : mode === "audio" ? (
                    <CanvasAudioSettingsPopover config={config} placement="topRight" buttonClassName="canvas-compact-control !h-10 !w-full !justify-start !rounded-lg !px-2" onConfigChange={(key, value) => onConfigChange(node.id, audioConfigPatch(key, value))} />
                ) : ecommerce ? (
                    <div className="canvas-compact-control flex h-10 items-center truncate rounded-lg border px-2 text-xs" style={chipStyle}>{t("canvas.configNode.items", { count: ecommerceCount })}</div>
                ) : (
                    <CanvasTextSettingsPopover config={config} count={node.metadata?.textCount || 1} placement="topRight" buttonClassName="canvas-compact-control !h-10 !w-full !justify-start !rounded-lg !px-2" onConfigChange={(_, value) => onConfigChange(node.id, { reasoningEffort: value })} onCountChange={(textCount) => onConfigChange(node.id, { textCount })} />
                )}
            </div>
            </div>

            <Button
                type="primary"
                className="mt-2 !h-9 !w-full !shrink-0 !cursor-pointer !rounded-lg"
                danger={isRunning}
                disabled={!isRunning && !canGenerate}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={() => (isRunning ? onStop(node.id) : onGenerate(node.id))}
            >
                <span className="inline-flex items-center gap-1.5">
                    {isRunning ? (
                        <>
                            <LoaderCircle className="size-4 animate-spin" />
                            <Square className="size-3.5 fill-current" />
                            <span>{t("canvas.configNode.stop")}</span>
                        </>
                    ) : (
                        <>
                            <Play className="size-4" />
                            <span>{ecommerce ? t(mode === "text" ? "canvas.configNode.generateTexts" : "canvas.configNode.generateCount", { count: ecommerceCount }) : t("canvas.configNode.generate")}</span>
                        </>
                    )}
                </span>
            </Button>
        </div>
    );
}

function InputChip({ label, value, style }: { label: string; value: string; style: CSSProperties }) {
    return (
        <div className="inline-flex h-7 items-center gap-1 rounded-md border px-2 text-[11px]" style={style}>
            <span>{label}</span>
            <span className="font-medium">{value}</span>
        </div>
    );
}

function buildNodeConfig(globalConfig: AiConfig, node: CanvasNodeData, mode: CanvasGenerationMode): AiConfig {
    return {
        ...globalConfig,
        model: resolveModelForCapability(globalConfig, node.metadata?.model, mode),
        reasoningEffort: node.metadata?.reasoningEffort || globalConfig.reasoningEffort || defaultConfig.reasoningEffort,
        quality: node.metadata?.quality || globalConfig.quality || defaultConfig.quality,
        size: node.metadata?.size || globalConfig.size || defaultConfig.size,
        background: node.metadata?.background ?? globalConfig.background ?? defaultConfig.background,
        videoSeconds: node.metadata?.seconds || globalConfig.videoSeconds || defaultConfig.videoSeconds,
        vquality: node.metadata?.vquality || globalConfig.vquality || defaultConfig.vquality,
        videoGenerateAudio: node.metadata?.generateAudio || globalConfig.videoGenerateAudio || defaultConfig.videoGenerateAudio,
        videoWatermark: node.metadata?.watermark || globalConfig.videoWatermark || defaultConfig.videoWatermark,
        videoMode: node.metadata?.videoMode || globalConfig.videoMode || defaultConfig.videoMode,
        audioVoice: node.metadata?.audioVoice || globalConfig.audioVoice || defaultConfig.audioVoice,
        audioFormat: node.metadata?.audioFormat || globalConfig.audioFormat || defaultConfig.audioFormat,
        audioSpeed: node.metadata?.audioSpeed || globalConfig.audioSpeed || defaultConfig.audioSpeed,
        audioInstructions: node.metadata?.audioInstructions || globalConfig.audioInstructions || defaultConfig.audioInstructions,
        count: String(node.metadata?.count || (mode === "image" ? globalConfig.canvasImageCount || globalConfig.count : globalConfig.count) || defaultConfig.count),
    };
}

function videoConfigPatch(key: keyof AiConfig, value: string) {
    if (key === "videoSeconds") return { seconds: value };
    if (key === "videoGenerateAudio") return { generateAudio: value };
    if (key === "videoWatermark") return { watermark: value };
    if (key === "videoMode") return { videoMode: value };
    return { [key]: value };
}

function audioConfigPatch(key: CanvasAudioSettingKey, value: string) {
    if (key === "audioVoice") return { audioVoice: value };
    if (key === "audioFormat") return { audioFormat: value };
    if (key === "audioSpeed") return { audioSpeed: value };
    return { audioInstructions: value };
}

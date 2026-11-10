import { useTranslation } from "react-i18next";

import { ECOMMERCE_PURPOSES, SENSENOVA_SIZES, readEcommercePurposes, readEcommerceSizes, toggleCsv } from "@/lib/canvas/ecommerce-options";
import type { CanvasNodeMetadata } from "@/types/canvas";

type EcommerceOptionsPanelProps = {
    mode: "image" | "text";
    metadata?: CanvasNodeMetadata;
    textColor: string;
    mutedColor: string;
    fill: string;
    onChange: (patch: Partial<CanvasNodeMetadata>) => void;
};

export function EcommerceOptionsPanel({ mode, metadata, textColor, mutedColor, fill, onChange }: EcommerceOptionsPanelProps) {
    const { t } = useTranslation();
    const purposes = readEcommercePurposes(metadata?.ecommercePurposes);
    const sizes = readEcommerceSizes(metadata?.ecommerceSizes);
    const selectedPurposes = new Set(purposes.map((item) => item.id));
    const selectedSizes = new Set(sizes);
    const watermark = metadata?.imageWatermark === "true";
    const promptExtend = metadata?.promptExtend === "true";

    return (
        <div className="mb-2 cursor-default" onMouseDown={(event) => event.stopPropagation()} onPointerDown={(event) => event.stopPropagation()}>
            {mode === "text" ? (
                <>
                    <OptionLabel color={mutedColor}>{t("canvas.ecommerce.purpose")}</OptionLabel>
                    <div className="mt-1 flex flex-wrap gap-1">
                        {ECOMMERCE_PURPOSES.map((item) => (
                            <Chip
                                key={item.id}
                                label={item.label}
                                selected={selectedPurposes.has(item.id)}
                                fill={fill}
                                textColor={textColor}
                                onClick={() => onChange({ ecommercePurposes: toggleCsv(metadata?.ecommercePurposes, item.id, "main") })}
                            />
                        ))}
                    </div>
                </>
            ) : null}
            {mode === "image" ? (
                <>
                    <OptionLabel color={mutedColor}>{t("canvas.ecommerce.ratio")}</OptionLabel>
                    <div className="mt-1 flex flex-wrap gap-1">
                        {SENSENOVA_SIZES.map((item) => (
                            <Chip
                                key={item.id}
                                label={item.hint === "4K" ? `${item.label} 4K` : item.label}
                                selected={selectedSizes.has(item.pixels)}
                                fill={fill}
                                textColor={textColor}
                                onClick={() => onChange({ ecommerceSizes: toggleCsv(metadata?.ecommerceSizes, item.pixels, "2048x2048") })}
                            />
                        ))}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                        <Chip label={t("canvas.ecommerce.watermark")} selected={watermark} fill={fill} textColor={textColor} onClick={() => onChange({ imageWatermark: watermark ? "false" : "true" })} />
                        <Chip label={t("canvas.ecommerce.promptExtend")} selected={promptExtend} fill={fill} textColor={textColor} onClick={() => onChange({ promptExtend: promptExtend ? "false" : "true" })} />
                    </div>
                </>
            ) : null}
            <p className="mt-1 text-[11px] leading-5" style={{ color: mutedColor }}>
                {mode === "image" ? t("canvas.ecommerce.imageHint") : t("canvas.ecommerce.textHint")}
            </p>
        </div>
    );
}

function OptionLabel({ children, color }: { children: string; color: string }) {
    return <div className="mt-1 text-[11px]" style={{ color }}>{children}</div>;
}

function Chip({ label, selected, fill, textColor, onClick }: { label: string; selected: boolean; fill: string; textColor: string; onClick: () => void }) {
    return (
        <button
            type="button"
            className="h-7 rounded-md border px-2 text-[11px]"
            style={{ background: selected ? textColor : fill, color: selected ? fill : textColor, borderColor: textColor }}
            onMouseDown={(event) => event.stopPropagation()}
            onPointerDown={(event) => event.stopPropagation()}
            onClick={onClick}
        >
            {label}
        </button>
    );
}

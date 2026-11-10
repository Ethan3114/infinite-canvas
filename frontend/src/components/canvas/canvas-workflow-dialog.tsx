import { Modal } from "antd";
import { useTranslation } from "react-i18next";

import type { CanvasWorkflow } from "@/lib/canvas/workflow";

export function CanvasWorkflowDialog({ open, onCancel, onCreate }: { open: boolean; onCancel: () => void; onCreate: (workflow: CanvasWorkflow) => void }) {
    const { t } = useTranslation();
    const choices: Array<{ id: CanvasWorkflow; title: string; hint: string }> = [
        { id: "ecommerce", title: t("canvas.workflow.ecommerce"), hint: t("canvas.workflow.ecommerceHint") },
        { id: "drama", title: t("canvas.workflow.drama"), hint: t("canvas.workflow.dramaHint") },
    ];
    return (
        <Modal open={open} title={t("canvas.workflow.title")} onCancel={onCancel} footer={null} centered destroyOnHidden>
            <p className="mb-4 text-sm leading-6 text-stone-500">{t("canvas.workflow.description")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
                {choices.map((choice) => (
                    <button key={choice.id} type="button" className="rounded-2xl bg-[#f1eee8] p-5 text-left transition hover:bg-[#ebe6dc] dark:bg-white/5 dark:hover:bg-white/10" onClick={() => onCreate(choice.id)}>
                        <span className="block text-lg font-semibold text-stone-950 dark:text-stone-100">{choice.title}</span>
                        <span className="mt-2 block text-sm leading-6 text-stone-600 dark:text-stone-400">{choice.hint}</span>
                    </button>
                ))}
            </div>
        </Modal>
    );
}

/** 画布从创建时就定下工作流。旧画布没有这个字段时，按电商处理。 */

export type CanvasWorkflow = "ecommerce" | "drama";

let activeWorkflow: CanvasWorkflow = "ecommerce";
let activeDramaTask = "summary";

export function normalizeWorkflow(value: unknown): CanvasWorkflow {
    return value === "drama" ? "drama" : "ecommerce";
}

export function setActiveWorkflow(value: CanvasWorkflow) {
    activeWorkflow = value;
}

export function getActiveWorkflow(): CanvasWorkflow {
    return activeWorkflow;
}

export function setActiveDramaTask(task: string) {
    activeDramaTask = task || "summary";
}

export function getActiveDramaTask(): string {
    return activeDramaTask;
}

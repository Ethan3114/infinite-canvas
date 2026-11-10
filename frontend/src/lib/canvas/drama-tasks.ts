/** 短剧一次只做一种。文字和图像按顺序分开，后面的图只用对应的那段文字。 */

export type DramaTaskKind = "text" | "image" | "video";

export type DramaTask = {
    id: string;
    kind: DramaTaskKind;
    labelKey: string;
    hintKey: string;
};

export const DRAMA_TASKS: DramaTask[] = [
    { id: "summary", kind: "text", labelKey: "canvas.dramaTask.summary", hintKey: "canvas.dramaTask.summaryHint" },
    { id: "character", kind: "text", labelKey: "canvas.dramaTask.character", hintKey: "canvas.dramaTask.characterHint" },
    { id: "prop", kind: "text", labelKey: "canvas.dramaTask.prop", hintKey: "canvas.dramaTask.propHint" },
    { id: "scene", kind: "text", labelKey: "canvas.dramaTask.scene", hintKey: "canvas.dramaTask.sceneHint" },
    { id: "plot", kind: "text", labelKey: "canvas.dramaTask.plot", hintKey: "canvas.dramaTask.plotHint" },
    { id: "shot", kind: "text", labelKey: "canvas.dramaTask.shot", hintKey: "canvas.dramaTask.shotHint" },
    { id: "characterImage", kind: "image", labelKey: "canvas.dramaTask.characterImage", hintKey: "canvas.dramaTask.characterImageHint" },
    { id: "propImage", kind: "image", labelKey: "canvas.dramaTask.propImage", hintKey: "canvas.dramaTask.propImageHint" },
    { id: "sceneImage", kind: "image", labelKey: "canvas.dramaTask.sceneImage", hintKey: "canvas.dramaTask.sceneImageHint" },
    { id: "shotImage", kind: "image", labelKey: "canvas.dramaTask.shotImage", hintKey: "canvas.dramaTask.shotImageHint" },
    { id: "clip", kind: "video", labelKey: "canvas.dramaTask.clip", hintKey: "canvas.dramaTask.clipHint" },
    { id: "join", kind: "video", labelKey: "canvas.dramaTask.join", hintKey: "canvas.dramaTask.joinHint" },
];

export function findDramaTask(id?: string): DramaTask {
    return DRAMA_TASKS.find((task) => task.id === id) || DRAMA_TASKS[0];
}

export function dramaImagePrompt(task: string | undefined, prompt: string): string {
    const body = prompt.trim();
    if (task === "characterImage") return `把这个角色的正视图、侧视图、背视图画在同一张图里，不要分成三张，不要换成另一个人。\n${body}`;
    if (task === "propImage") return `只画道具，不要画完整剧情，不要把主角画进去。\n${body}`;
    if (task === "sceneImage") return `只画场景。不要换成另一个主角，避免画面发空、左右完全对称、主体死死居中。\n${body}`;
    if (task === "shotImage") return `只画这一镜的一张画面。人物、场景和道具如果有参考图，必须跟着参考图，不要另造主角。\n${body}`;
    return body;
}

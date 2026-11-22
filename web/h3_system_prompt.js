import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "BK.LlamaCpp.H3SystemPrompt",
    nodeCreated(node) {
        if (node.comfyClass !== "llama_cpp_instruct_adv" && node.constructor.comfyClass !== "llama_cpp_instruct_adv") return;

        const mode = node.widgets?.find((widget) => widget.name === "H3_story_enhancer");
        const systemPrompt = node.widgets?.find((widget) => widget.name === "system_prompt");
        if (!mode || !systemPrompt) return;

        const update = (value = mode.value) => {
            const inactive = value != null && value !== "off";
            systemPrompt.disabled = inactive;
            node.updateComputedDisabled?.();
            node.setDirtyCanvas?.(true, true);
        };

        const originalCallback = mode.callback;
        mode.callback = function (value, ...args) {
            const result = originalCallback?.call(this, value, ...args);
            update(value);
            return result;
        };

        const originalConfigure = node.onConfigure;
        node.onConfigure = function (...args) {
            const result = originalConfigure?.apply(this, args);
            update();
            return result;
        };

        update();
    },
});

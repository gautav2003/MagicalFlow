document.addEventListener('DOMContentLoaded', () => {
    const generateBtn = document.getElementById('btn-generate');
    if (!generateBtn) return;

    generateBtn.addEventListener('click', async () => {
        const promptInput = document.getElementById('ai-prompt');
        const prompt = promptInput ? promptInput.value.trim() : "";

        if (!prompt) {
            alert("Please enter a prompt for the AI generator!");
            return;
        }

        generateBtn.disabled = true;
        generateBtn.textContent = "Synthesizing...";

        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, genre: "Pro Studio" })
            });

            if (response.ok) {
                // Reload the studio output page to render the newly generated database track/stem
                location.reload();
            } else {
                alert("Generation failed. Please try again.");
                generateBtn.disabled = false;
                generateBtn.textContent = "Generate Stem";
            }
        } catch (error) {
            console.error("Error connecting to AI stem generation API:", error);
            alert("Network error connecting to backend.");
            generateBtn.disabled = false;
            generateBtn.textContent = "Generate Stem";
        }
    });
});
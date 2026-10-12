document.addEventListener('DOMContentLoaded', () => {
    const generateBtn = document.getElementById('btn-generate');
    if (!generateBtn) return;

    generateBtn.addEventListener('click', async () => {
        const promptInput = document.getElementById('ai-prompt');
        const genreSelect = document.getElementById('ai-genre');
        const statusDiv = document.getElementById('generation-status');

        const prompt = promptInput.value.trim();
        const genre = genreSelect.value;

        if (!prompt) {
            statusDiv.textContent = "Please enter an audio prompt description!";
            statusDiv.style.color = "#f87171";
            return;
        }

        generateBtn.disabled = true;
        generateBtn.textContent = "Synthesizing Stem...";
        statusDiv.textContent = "Connecting to generative backend model...";
        statusDiv.style.color = "#a1a1aa";

        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, genre })
            });

            if (response.ok) {
                statusDiv.textContent = "Stem generated successfully! Reloading studio...";
                statusDiv.style.color = "#34d399";
                setTimeout(() => location.reload(), 600);
            } else {
                statusDiv.textContent = "Generation failed. Try again.";
                statusDiv.style.color = "#f87171";
                generateBtn.disabled = false;
                generateBtn.textContent = "Generate Audio Stem";
            }
        } catch (error) {
            console.error("Error:", error);
            statusDiv.textContent = "Network error connecting to Flask backend.";
            statusDiv.style.color = "#f87171";
            generateBtn.disabled = false;
            generateBtn.textContent = "Generate Audio Stem";
        }
    });
});
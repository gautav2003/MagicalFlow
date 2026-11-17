# Magical Flow AI setup

## Maya artist-support chat

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey). Key availability, quotas, and pricing depend on Google's current terms and your account.
2. In the `Magical Flow` project folder, add these settings to the existing `.env` file:

   ```text
   GEMINI_API_KEY=your-key
   GEMINI_MODEL=gemini-2.0-flash
   ```

   You can use [.env.example](./.env.example) as a reference. Keep `.env` private; never paste a key into chat or browser code.
3. Restart the Flask app. Maya's assistant status should show **Gemini AI connected**. If the key is not configured, Maya provides local studio help instead.

The Gemini key is read only by the Flask server. A provider/network error is shown in chat and logged by the server; the app does not silently pretend an AI response was generated.

## Music generation

Beginner mode creates playable, browser-rendered instrumental arrangements, and Pro Studio provides its in-browser studio/sequencer tools. These work without a cloud API key but do not generate complete AI-produced audio from text. A separate AI audio provider is needed for that capability; such services may require paid credits, so a free API key cannot be guaranteed.

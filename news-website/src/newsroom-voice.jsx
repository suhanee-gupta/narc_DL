export function playVoice(headline, author, topic) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(`${topic}. ${headline}. By ${author || 'The Margin Staff'}.`);
  u.rate = 0.95;
  u.pitch = 0.95;
  
  // Attempt premium voice mapping
  const voices = window.speechSynthesis.getVoices();
  const best = voices.find(v => v.name.includes("Premium") || v.name.includes("Google UK English Female") || v.name.includes("Samantha") || v.name.includes("Daniel"));
  if (best) u.voice = best;

  window.speechSynthesis.speak(u);
}

export function stopVoice() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

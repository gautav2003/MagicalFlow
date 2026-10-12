// Password strength indicator logic for Register page
function checkPasswordStrength() {
    const passwordInput = document.getElementById('password');
    const bar = document.getElementById('strengthBar');
    const text = document.getElementById('strengthText');
    
    if (!passwordInput || !bar || !text) return;

    const val = passwordInput.value;
    let score = 0;
    
    if (val.length > 5) score++;
    if (val.length > 9) score++;
    if (/[A-Z]/.test(val)) score++;
    if (/[0-9]/.test(val)) score++;
    if (/[^A-Za-z0-9]/.test(val)) score++;

    bar.className = "h-full transition-all duration-300";
    if (val.length === 0) {
        bar.style.width = "0%";
        text.innerText = "";
    } else if (score <= 2) {
        bar.style.width = "25%";
        bar.classList.add("bg-red-500");
        text.innerText = "Weak Password";
        text.className = "text-[10px] text-red-400 mt-1 text-right";
    } else if (score === 3) {
        bar.style.width = "50%";
        bar.classList.add("bg-orange-500");
        text.innerText = "Medium Password";
        text.className = "text-[10px] text-orange-400 mt-1 text-right";
    } else if (score === 4) {
        bar.style.width = "75%";
        bar.classList.add("bg-yellow-400");
        text.innerText = "Strong Password";
        text.className = "text-[10px] text-yellow-300 mt-1 text-right";
    } else {
        bar.style.width = "100%";
        bar.classList.add("bg-green-500");
        text.innerText = "Excellent Password";
        text.className = "text-[10px] text-green-400 mt-1 text-right";
    }
}
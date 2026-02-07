document.addEventListener("DOMContentLoaded", () => {
  const dotsButtons = document.querySelectorAll(".dots-btn");

  dotsButtons.forEach(button => {
    button.addEventListener("click", (e) => {
      e.stopPropagation();
      const dropdown = button.nextElementSibling;
      dropdown.style.display = dropdown.style.display === "flex" ? "none" : "flex";
    });
  });

  document.addEventListener("click", () => {
    document.querySelectorAll(".dropdown").forEach(drop => {
      drop.style.display = "none";
    });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.querySelector("#sidebarToggleBtn");
  const sidebar = document.getElementById("pdfSidebarDrawer");

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", () => {
      toggleBtn.classList.toggle("active");
      sidebar.classList.toggle("active");
    });
  } else {
    console.warn("Toggle button or sidebar not found.");
  }
});

function getTimeGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning, Manmath";
  if (hour < 17) return "Good afternoon, Manmath";
  if (hour < 21) return "Good evening, Manmath";
  return "Good evening, Manmath";
}

const greetingEl = document.getElementById("greeting-message");
const greetingLine1 = document.getElementById("greeting-line1");

if (greetingLine1) {
  greetingLine1.textContent = getTimeGreeting();
}

function hideGreeting() {
  if (greetingEl && !greetingEl.classList.contains("fade-out")) {
    greetingEl.classList.add("fade-out");
  }
}
